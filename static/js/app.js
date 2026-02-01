// Among Us IRL - PWA App JavaScript

// Register service worker for PWA
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/static/sw.js')
            .then(reg => console.log('Service Worker registered'))
            .catch(err => console.log('Service Worker registration failed:', err));
    });
}

// Utility functions
function vibrate(pattern) {
    if (navigator.vibrate) {
        navigator.vibrate(pattern);
    }
}

// Prevent pull-to-refresh on mobile (can interfere with scrolling)
document.body.addEventListener('touchmove', function(e) {
    if (e.target.closest('.scrollable')) return;
    if (document.body.scrollTop === 0) {
        e.preventDefault();
    }
}, { passive: false });
