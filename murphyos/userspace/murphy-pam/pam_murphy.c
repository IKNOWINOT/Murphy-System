/*
 * pam_murphy.c — PAM module for MurphyOS session and authentication
 *
 * © 2020 Inoni Limited Liability Company, Creator: Corey Post
 * License: BSL 1.1
 *
 * Provides:
 *   pam_sm_open_session   — creates a Murphy session on login
 *   pam_sm_close_session  — destroys the Murphy session on logout
 *   pam_sm_authenticate   — (paranoid mode) checks HITL gate before sudo
 *
 * Build:
 *   gcc -fPIC -shared -o pam_murphy.so pam_murphy.c -lpam -lcurl
 *
 * Design principles:
 *   - Thread-safe: no global mutable state; all state on stack.
 *   - Fail-open: returns PAM_IGNORE when Murphy is unreachable so that
 *     login is never blocked by a Murphy outage.
 *   - Configurable via /etc/murphy/pam.conf.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <fcntl.h>
#include <unistd.h>
#include <syslog.h>

#include <security/pam_modules.h>
#include <security/pam_ext.h>
#include <curl/curl.h>

/* ------------------------------------------------------------------------ */
/* Constants                                                                 */
/* ------------------------------------------------------------------------ */

#define MURPHY_PAM_CONFIG    "/etc/murphy/pam.conf"
#define MURPHY_SESSION_KEY   "murphy_session_id"
#define MURPHY_CONFIDENCE    "/murphy/live/confidence"
#define MURPHY_EVENT_DEV     "/dev/murphy-event"

#define DEFAULT_MURPHY_URL   "http://localhost:8000"
#define DEFAULT_SAFETY_LEVEL "standard"
#define DEFAULT_TIMEOUT      5L

#define URL_BUFSIZE          1024
#define RESP_BUFSIZE         4096
#define LINE_BUFSIZE         256
#define CONFIDENCE_BUFSIZE   64
#define CONFIG_URL_BUFSIZE   256

#define CONFIDENCE_THRESHOLD 0.50

/* ------------------------------------------------------------------------ */
/* Configuration                                                             */
/* ------------------------------------------------------------------------ */

struct murphy_config {
    char murphy_url[CONFIG_URL_BUFSIZE];
    char safety_level[LINE_BUFSIZE];
    long timeout;
};

static void config_defaults(struct murphy_config *cfg)
{
    snprintf(cfg->murphy_url, sizeof(cfg->murphy_url), "%s", DEFAULT_MURPHY_URL);
    snprintf(cfg->safety_level, sizeof(cfg->safety_level), "%s", DEFAULT_SAFETY_LEVEL);
    cfg->timeout = DEFAULT_TIMEOUT;
}

static void config_load(struct murphy_config *cfg)
{
    FILE *fp;
    char line[LINE_BUFSIZE];

    config_defaults(cfg);

    fp = fopen(MURPHY_PAM_CONFIG, "r");
    if (!fp)
        return;

    while (fgets(line, sizeof(line), fp)) {
        char *nl = strchr(line, '\n');
        if (nl) *nl = '\0';

        /* skip comments and blank lines */
        if (line[0] == '#' || line[0] == '\0')
            continue;

        char *eq = strchr(line, '=');
        if (!eq)
            continue;

        *eq = '\0';
        char *key = line;
        char *val = eq + 1;

        if (strcmp(key, "murphy_url") == 0)
            snprintf(cfg->murphy_url, sizeof(cfg->murphy_url), "%s", val);
        else if (strcmp(key, "safety_level") == 0)
            snprintf(cfg->safety_level, sizeof(cfg->safety_level), "%s", val);
        else if (strcmp(key, "timeout") == 0)
            cfg->timeout = strtol(val, NULL, 10);
    }

    fclose(fp);
}

/* ------------------------------------------------------------------------ */
/* cURL helpers                                                              */
/* ------------------------------------------------------------------------ */

struct response_buf {
    char   data[RESP_BUFSIZE];
    size_t len;
};

static size_t write_callback(char *ptr, size_t size, size_t nmemb,
                             void *userdata)
{
    struct response_buf *buf = (struct response_buf *)userdata;
    size_t bytes = size * nmemb;
    size_t space = sizeof(buf->data) - buf->len - 1;

    if (bytes > space)
        bytes = space;

    memcpy(buf->data + buf->len, ptr, bytes);
    buf->len += bytes;
    buf->data[buf->len] = '\0';
    return size * nmemb;
}

/*
 * Perform an HTTP request. Returns 0 on success, -1 on failure.
 * response_out (if not NULL) receives the body.
 */
static int murphy_http(const struct murphy_config *cfg,
                       const char *method, const char *url,
                       const char *post_body,
                       struct response_buf *response_out)
{
    CURL *curl;
    CURLcode res;
    struct curl_slist *headers = NULL;
    struct response_buf resp;
    long http_code = 0;

    memset(&resp, 0, sizeof(resp));

    curl = curl_easy_init();
    if (!curl)
        return -1;

    headers = curl_slist_append(headers, "Content-Type: application/json");

    curl_easy_setopt(curl, CURLOPT_URL, url);
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, cfg->timeout);
    curl_easy_setopt(curl, CURLOPT_CONNECTTIMEOUT, cfg->timeout);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_callback);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &resp);
    curl_easy_setopt(curl, CURLOPT_NOSIGNAL, 1L);

    if (strcmp(method, "POST") == 0) {
        curl_easy_setopt(curl, CURLOPT_POST, 1L);
        curl_easy_setopt(curl, CURLOPT_POSTFIELDS, post_body ? post_body : "");
    } else if (strcmp(method, "DELETE") == 0) {
        curl_easy_setopt(curl, CURLOPT_CUSTOMREQUEST, "DELETE");
    }

    res = curl_easy_perform(curl);
    if (res == CURLE_OK)
        curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &http_code);

    curl_slist_free_all(headers);
    curl_easy_cleanup(curl);

    if (res != CURLE_OK || http_code < 200 || http_code >= 300)
        return -1;

    if (response_out)
        *response_out = resp;

    return 0;
}

/* ------------------------------------------------------------------------ */
/* PAM data cleanup callback                                                 */
/* ------------------------------------------------------------------------ */

static void murphy_cleanup(pam_handle_t *pamh, void *data, int error_status)
{
    (void)pamh;
    (void)error_status;
    free(data);
}

/* ------------------------------------------------------------------------ */
/* Minimal JSON helpers (no external dependency)                             */
/* ------------------------------------------------------------------------ */

/*
 * Extract a simple string value for a given key from a flat JSON object.
 * Writes result into out (up to out_sz). Returns 0 on success.
 */
static int json_extract_string(const char *json, const char *key,
                               char *out, size_t out_sz)
{
    char needle[LINE_BUFSIZE];
    const char *p, *start, *end;

    snprintf(needle, sizeof(needle), "\"%s\"", key);
    p = strstr(json, needle);
    if (!p)
        return -1;

    p = strchr(p + strlen(needle), ':');
    if (!p)
        return -1;

    /* skip whitespace and opening quote */
    while (*p == ':' || *p == ' ' || *p == '\t') p++;
    if (*p != '"')
        return -1;

    start = p + 1;
    end = strchr(start, '"');
    if (!end)
        return -1;

    size_t len = (size_t)(end - start);
    if (len >= out_sz)
        len = out_sz - 1;

    memcpy(out, start, len);
    out[len] = '\0';
    return 0;
}

/* ------------------------------------------------------------------------ */
/* Session management                                                        */
/* ------------------------------------------------------------------------ */

PAM_EXTERN int pam_sm_open_session(pam_handle_t *pamh, int flags,
                                   int argc, const char **argv)
{
    const char *username = NULL;
    struct murphy_config cfg;
    struct response_buf resp;
    char url[URL_BUFSIZE];
    char post_body[URL_BUFSIZE];
    char session_id[LINE_BUFSIZE];
    int rc;

    (void)flags;
    (void)argc;
    (void)argv;

    config_load(&cfg);

    rc = pam_get_user(pamh, &username, NULL);
    if (rc != PAM_SUCCESS || !username) {
        pam_syslog(pamh, LOG_WARNING,
                   "murphy: could not determine username");
        return PAM_IGNORE;
    }

    snprintf(url, sizeof(url), "%s/api/session/create", cfg.murphy_url);
    snprintf(post_body, sizeof(post_body),
             "{\"username\":\"%s\"}", username);

    memset(&resp, 0, sizeof(resp));
    if (murphy_http(&cfg, "POST", url, post_body, &resp) != 0) {
        pam_syslog(pamh, LOG_INFO,
                   "murphy: session create failed for %s (Murphy may be down)",
                   username);
        return PAM_IGNORE;
    }

    if (json_extract_string(resp.data, "session_id",
                            session_id, sizeof(session_id)) == 0) {
        /* Store session ID so close_session can use it */
        char *stored = strdup(session_id);
        if (stored)
            pam_set_data(pamh, MURPHY_SESSION_KEY, stored, murphy_cleanup);

        pam_syslog(pamh, LOG_INFO,
                   "murphy: opened session %s for %s", session_id, username);
    }

    return PAM_SUCCESS;
}

PAM_EXTERN int pam_sm_close_session(pam_handle_t *pamh, int flags,
                                    int argc, const char **argv)
{
    const char *session_id = NULL;
    struct murphy_config cfg;
    char url[URL_BUFSIZE];
    int rc;

    (void)flags;
    (void)argc;
    (void)argv;

    config_load(&cfg);

    rc = pam_get_data(pamh, MURPHY_SESSION_KEY,
                      (const void **)&session_id);
    if (rc != PAM_SUCCESS || !session_id) {
        /* No session was created — nothing to close */
        return PAM_SUCCESS;
    }

    snprintf(url, sizeof(url), "%s/api/session/%s",
             cfg.murphy_url, session_id);

    if (murphy_http(&cfg, "DELETE", url, NULL, NULL) != 0) {
        pam_syslog(pamh, LOG_INFO,
                   "murphy: session close failed for %s (Murphy may be down)",
                   session_id);
        return PAM_IGNORE;
    }

    pam_syslog(pamh, LOG_INFO,
               "murphy: closed session %s", session_id);
    return PAM_SUCCESS;
}

/* ------------------------------------------------------------------------ */
/* Authentication — paranoid-mode HITL gate                                  */
/* ------------------------------------------------------------------------ */

static double read_confidence(void)
{
    FILE *fp;
    char buf[CONFIDENCE_BUFSIZE];
    double val = 1.0;  /* assume safe if unreadable */

    fp = fopen(MURPHY_CONFIDENCE, "r");
    if (!fp)
        return val;

    if (fgets(buf, sizeof(buf), fp))
        val = strtod(buf, NULL);

    fclose(fp);
    return val;
}

static int request_hitl_approval(pam_handle_t *pamh, const char *username)
{
    int fd;
    char msg[URL_BUFSIZE];
    int written;

    fd = open(MURPHY_EVENT_DEV, O_WRONLY | O_NONBLOCK);
    if (fd < 0) {
        pam_syslog(pamh, LOG_WARNING,
                   "murphy: cannot open %s for HITL request: %s",
                   MURPHY_EVENT_DEV, strerror(errno));
        return -1;
    }

    written = snprintf(msg, sizeof(msg),
             "{\"event\":\"hitl_approval_request\","
             "\"username\":\"%s\",\"action\":\"sudo\"}\n",
             username);

    if (write(fd, msg, (size_t)written) < 0) {
        pam_syslog(pamh, LOG_WARNING,
                   "murphy: HITL write failed: %s", strerror(errno));
        close(fd);
        return -1;
    }

    close(fd);
    return 0;
}

PAM_EXTERN int pam_sm_authenticate(pam_handle_t *pamh, int flags,
                                   int argc, const char **argv)
{
    const char *username = NULL;
    struct murphy_config cfg;
    double confidence;
    int rc;

    (void)flags;
    (void)argc;
    (void)argv;

    config_load(&cfg);

    /* Only the "paranoid" safety level gates authentication */
    if (strcmp(cfg.safety_level, "paranoid") != 0)
        return PAM_IGNORE;

    rc = pam_get_user(pamh, &username, NULL);
    if (rc != PAM_SUCCESS || !username)
        return PAM_IGNORE;

    confidence = read_confidence();
    if (confidence >= CONFIDENCE_THRESHOLD) {
        pam_syslog(pamh, LOG_DEBUG,
                   "murphy: confidence %.2f >= %.2f, allowing %s",
                   confidence, CONFIDENCE_THRESHOLD, username);
        return PAM_SUCCESS;
    }

    pam_syslog(pamh, LOG_NOTICE,
               "murphy: confidence %.2f < %.2f — requesting HITL approval for %s",
               confidence, CONFIDENCE_THRESHOLD, username);

    if (request_hitl_approval(pamh, username) != 0) {
        pam_syslog(pamh, LOG_WARNING,
                   "murphy: HITL request failed — allowing %s (fail-open)",
                   username);
        return PAM_IGNORE;
    }

    pam_syslog(pamh, LOG_NOTICE,
               "murphy: HITL approval requested for %s — denying pending approval",
               username);
    return PAM_AUTH_ERR;
}

/* ------------------------------------------------------------------------ */
/* Stubs for unused PAM entry points                                         */
/* ------------------------------------------------------------------------ */

PAM_EXTERN int pam_sm_setcred(pam_handle_t *pamh, int flags,
                              int argc, const char **argv)
{
    (void)pamh;
    (void)flags;
    (void)argc;
    (void)argv;
    return PAM_SUCCESS;
}

PAM_EXTERN int pam_sm_acct_mgmt(pam_handle_t *pamh, int flags,
                                int argc, const char **argv)
{
    (void)pamh;
    (void)flags;
    (void)argc;
    (void)argv;
    return PAM_IGNORE;
}

PAM_EXTERN int pam_sm_chauthtok(pam_handle_t *pamh, int flags,
                                int argc, const char **argv)
{
    (void)pamh;
    (void)flags;
    (void)argc;
    (void)argv;
    return PAM_IGNORE;
}
