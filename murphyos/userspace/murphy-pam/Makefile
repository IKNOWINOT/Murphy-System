# Makefile — Build pam_murphy.so
# © 2020 Inoni Limited Liability Company, Creator: Corey Post
# License: BSL 1.1

CC       ?= gcc
CFLAGS   := -fPIC -Wall -Wextra -Werror -O2
LDFLAGS  := -shared -lpam -lcurl

TARGET   := pam_murphy.so
SRC      := pam_murphy.c

# Detect install path (Debian/Ubuntu vs Red Hat/Fedora)
PAM_DIR  := $(shell [ -d /lib/security ] && echo /lib/security || echo /usr/lib/security)
CONF_DIR := /etc/murphy
HELPER_DIR := /usr/lib/murphy

.PHONY: all clean install uninstall

all: $(TARGET)

$(TARGET): $(SRC)
	$(CC) $(CFLAGS) -o $@ $< $(LDFLAGS)

clean:
	rm -f $(TARGET)

install: $(TARGET)
	install -d $(DESTDIR)$(PAM_DIR)
	install -m 0755 $(TARGET) $(DESTDIR)$(PAM_DIR)/
	install -d $(DESTDIR)$(CONF_DIR)
	install -m 0644 pam.conf $(DESTDIR)$(CONF_DIR)/pam.conf

uninstall:
	rm -f $(DESTDIR)$(PAM_DIR)/$(TARGET)
	rm -f $(DESTDIR)$(CONF_DIR)/pam.conf
