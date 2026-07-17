"""
Stealth evasions to reduce headless-browser detection.

These are applied via page.add_init_script() so they run BEFORE any page
script executes. They patch the most common fingerprint signals that bot
detectors (Akamai, DataDome, PerimeterX) check for.

This is a free, best-effort approach. It may not defeat a fully-tuned
Akamai Bot Manager deployment — if it doesn't, the fallback is residential
proxies or a commercial unblocker API.
"""
from __future__ import annotations

# JS injected before page load to mask automation signals.
STEALTH_INIT_SCRIPT = """
// navigator.webdriver → undefined (biggest tell)
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

// Mock a realistic chrome runtime object
window.chrome = window.chrome || {};
window.chrome.runtime = window.chrome.runtime || {};

// Plugins: headless Chrome reports 0 plugins
Object.defineProperty(navigator, 'plugins', {
    get: () => [
        { name: 'Chrome PDF Plugin' },
        { name: 'Chrome PDF Viewer' },
        { name: 'Native Client' },
    ],
});

// Languages
Object.defineProperty(navigator, 'languages', {
    get: () => ['en-US', 'en'],
});

// Permissions query (headless returns 'denied' oddly for notifications)
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications'
        ? Promise.resolve({ state: Notification.permission })
        : originalQuery(parameters)
);

// WebGL vendor/renderer spoofing (headless often reports SwiftShader)
const getParameter = WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter = function (parameter) {
    if (parameter === 37445) return 'Intel Inc.';           // UNMASKED_VENDOR_WEBGL
    if (parameter === 37446) return 'Intel Iris OpenGL Engine'; // UNMASKED_RENDERER_WEBGL
    return getParameter.call(this, parameter);
};

// Hairline feature / hardwareConcurrency sanity
Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
"""


# Chromium's real UA for a given major version. Keep this matched to the
# actual browser build — a mismatched UA is itself a detection signal.
# Update the major version if you upgrade the bundled Chromium.
DEFAULT_STEALTH_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
