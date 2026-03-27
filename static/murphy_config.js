/**
 * Murphy System - Client Configuration
 * 
 * This file provides runtime configuration for HTML UIs.
 * It reads from environment-specific settings and provides
 * sensible defaults for development.
 * 
 * Usage in HTML:
 *   <script src="/static/murphy_config.js"></script>
 *   <script>
 *     fetch(MURPHY_API_URL + '/api/health')
 *   </script>
 * 
 * @copyright 2020 Inoni Limited Liability Company
 * @license BSL-1.1
 */

(function(window) {
    'use strict';

    // =========================================================================
    // Configuration Detection
    // =========================================================================
    
    /**
     * Detect the API base URL from various sources:
     * 1. window.MURPHY_CONFIG (set by server-side template)
     * 2. Meta tag <meta name="murphy-api-url" content="...">
     * 3. Same-origin (current hostname, port 8000)
     * 4. Development fallback (localhost:8000)
     */
    function detectApiUrl() {
        // 1. Check for server-injected config
        if (window.MURPHY_CONFIG && window.MURPHY_CONFIG.apiUrl) {
            return window.MURPHY_CONFIG.apiUrl;
        }

        // 2. Check for meta tag
        const metaTag = document.querySelector('meta[name="murphy-api-url"]');
        if (metaTag && metaTag.content) {
            return metaTag.content;
        }

        // 3. Same-origin detection (production mode)
        const currentHost = window.location.hostname;
        const currentProtocol = window.location.protocol;
        
        // If we're on murphy.systems or similar, use same origin
        if (currentHost !== 'localhost' && currentHost !== '127.0.0.1') {
            // Use current origin with /api prefix
            return `${currentProtocol}//${currentHost}`;
        }

        // 4. Development fallback
        return 'http://localhost:8000';
    }

    /**
     * Detect WebSocket URL for real-time features
     */
    function detectWsUrl() {
        const apiUrl = detectApiUrl();
        return apiUrl.replace(/^http/, 'ws') + '/ws';
    }

    // =========================================================================
    // Global Configuration Object
    // =========================================================================

    const config = {
        // API Configuration
        apiUrl: detectApiUrl(),
        wsUrl: detectWsUrl(),
        
        // API Endpoints
        endpoints: {
            health: '/api/health',
            status: '/api/status',
            chat: '/api/chat',
            execute: '/api/execute',
            sessions: '/api/sessions',
            founder: '/api/founder',
            game: '/api/game',
            trading: '/api/trading',
        },

        // Feature Flags
        features: {
            e2ee: false,  // Set to true when matrix-nio is integrated
            realtime: true,
            analytics: true,
        },

        // UI Configuration
        ui: {
            theme: 'dark',
            animationsEnabled: true,
            debugMode: window.location.hostname === 'localhost',
        },

        // Helper Methods
        getEndpoint: function(name) {
            const endpoint = this.endpoints[name];
            return endpoint ? this.apiUrl + endpoint : null;
        },

        fetch: function(endpoint, options = {}) {
            const url = this.apiUrl + endpoint;
            return window.fetch(url, {
                ...options,
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers,
                },
            });
        },
    };

    // =========================================================================
    // Export to Global Scope
    // =========================================================================

    // Primary API URL constant (for backward compatibility)
    window.MURPHY_API_URL = config.apiUrl;
    window.MURPHY_WS_URL = config.wsUrl;

    // Full configuration object
    window.MurphyConfig = config;

    // Console notification in debug mode
    if (config.ui.debugMode) {
        console.log('[Murphy] Configuration loaded:', {
            apiUrl: config.apiUrl,
            wsUrl: config.wsUrl,
        });
    }

})(window);
