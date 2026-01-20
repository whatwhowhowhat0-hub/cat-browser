(function() {
    'use strict';
    
    console.log('adblocker activated');
    

    const blockedDomains = [

        'doubleclick.net',
        'googleadservices.com',
        'googlesyndication.com',
        'google-analytics.com',
        'googletagservices.com',
        'gstatic.com/cv/js/sender/',
        'adservice.google.com',       
        'facebook.com/tr',
        'connect.facebook.net',
        'adsystem.com',
        'adnxs.com',
        'amazon-adsystem.com',
        'scorecardresearch.com',
        'quantserve.com',
        '2mdn.net',
        'advertising.com',
        'outbrain.com',
        'taboola.com',
        'revcontent.com',
        'zemanta.com',
        '/ads/',
        '/advertising/',
        '/tracking/',
        '/analytics/',
        '/beacon/',
        '/pixel/'
    ];
    const adSelectors = [
        '.adsbygoogle',
        '[id*="google_ads"]',
        '[id*="div-gpt-ad"]',
        '[data-ad]',
        '[data-ad-type]',
        '[data-ad-client]',
        '[data-ad-slot]',
        '.ad-unit',
        '.ad-container',
        '.ad-wrapper',
        '.ad-frame',
        '.ad-placement',
        '[class*="sponsored"]',
        '[class*="promoted"]',
        '.is-sponsored',
        '.is-promoted',
        '.popup-ad',
        '.overlay-ad',
        '.modal-ad',
        '.lightbox-ad',
        '.video-ads',
        '.ad-video',
        '.instream-ad',
        '.outbrain',
        '.taboola',
        '.revcontent',
        '.zemanta',
        '.content-ad',
        '.native-ad'
    ];
    
    const originalFetch = window.fetch;
    window.fetch = function(...args) {
        const url = args[0];
        if (typeof url === 'string' && blockedDomains.some(domain => url.includes(domain))) {
            console.log(' Blocked ad request:', url.substring(0, 80));
            return Promise.reject(new Error('Blocked by AdBlocker'));
        }
        return originalFetch.apply(this, args);
    };
    
    const originalOpen = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function(method, url, ...rest) {
        if (typeof url === 'string' && blockedDomains.some(domain => url.includes(domain))) {
            this._blocked = true;
            console.log(' Blocked ad XHR:', url.substring(0, 80));
            return;
        }
        return originalOpen.call(this, method, url, ...rest);
    };
    
    XMLHttpRequest.prototype.send = function(...args) {
        if (this._blocked) return;
        return XMLHttpRequest.prototype.send.apply(this, args);
    };
    
    function removeRealAds() {
        adSelectors.forEach(selector => {
            try {
                const elements = document.querySelectorAll(selector);
                elements.forEach(element => {
                    if (isDefinitelyAnAd(element)) {
                        element.remove();
                        console.log(' Removed ad:', selector);
                    }
                });
            } catch(e) {
            }
        });
        
        document.querySelectorAll('iframe').forEach(iframe => {
            try {
                const src = iframe.src;
                if (src && blockedDomains.some(domain => src.includes(domain))) {
                    iframe.remove();
                    console.log(' Removed ad iframe');
                }
            } catch(e) {}
        });
    }
    

    function isDefinitelyAnAd(element) {
        if (!element || !element.getBoundingClientRect) return false;
        

        const style = window.getComputedStyle(element);
        if (style.display === 'none' || style.visibility === 'hidden') return true;
        

        const rect = element.getBoundingClientRect();
        const commonAdSizes = [
            {w: 728, h: 90},  
            {w: 300, h: 250}, 
            {w: 160, h: 600}, 
            {w: 320, h: 50},  
            {w: 300, h: 600},  
            {w: 970, h: 250},  
        ];
        
        const isExactAdSize = commonAdSizes.some(size => 
            Math.abs(rect.width - size.w) <= 2 && Math.abs(rect.height - size.h) <= 2
        );
        

        const text = (element.textContent || '').toLowerCase();
        const adKeywords = ['advertisement', 'sponsored', 'promoted', 'ads by', 'brought to you by'];
        const hasAdText = adKeywords.some(keyword => text.includes(keyword));
        

        const html = element.outerHTML.toLowerCase();
        const isGoogleAd = html.includes('adsbygoogle') || 
                          html.includes('google_ad') ||
                          html.includes('doubleclick');
        

        return isExactAdSize || hasAdText || isGoogleAd;
    }
    

    function handleCookieBanners() {
        const cookieSelectors = [
            '#cookieNotice',
            '#cookie-consent',
            '.cookie-banner',
            '.cookie-notice',
            '.gdpr-banner',
            '.cc_banner'
        ];
        
        cookieSelectors.forEach(selector => {
            try {
                const elements = document.querySelectorAll(selector);
                elements.forEach(element => {

                    element.style.display = 'none';
                });
            } catch(e) {}
        });
    }
    

    function handleYouTubeAds() {
        if (!window.location.hostname.includes('youtube.com')) return;
        
        const ytAdSelectors = [
            '.ytd-ad-slot-renderer',
            '.ytd-promoted-sparkles-web-renderer',
            '.ytd-action-companion-ad-renderer',
            '#player-ads',
            '.ytp-ad-module',
            '.video-ads'
        ];
        
        ytAdSelectors.forEach(selector => {
            try {
                document.querySelectorAll(selector).forEach(element => element.remove());
            } catch(e) {}
        });
        

        const video = document.querySelector('video');
        if (video) {
            video.addEventListener('timeupdate', function() {
                const adElement = document.querySelector('.ad-showing, .ad-interstitial');
                if (adElement && video.duration > 0 && video.duration < 120) {
                    video.currentTime = video.duration;
                }
            });
        }
    }

    const observer = new MutationObserver((mutations) => {
        let shouldCheck = false;
        mutations.forEach((mutation) => {
            if (mutation.addedNodes.length > 0) {
                mutation.addedNodes.forEach(node => {
                    if (node.nodeType === 1) { // Element node
                        const html = node.outerHTML || '';
                        if (html.includes('ad') || html.includes('google_ad') || html.includes('sponsored')) {
                            shouldCheck = true;
                        }
                    }
                });
            }
        });
        
        if (shouldCheck) {
            setTimeout(() => {
                removeRealAds();
                handleYouTubeAds();
            }, 500);
        }
    });
    

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            removeRealAds();
            handleCookieBanners();
            handleYouTubeAds();
            observer.observe(document.body, {
                childList: true,
                subtree: true
            });
        });
    } else {
        removeRealAds();
        handleCookieBanners();
        handleYouTubeAds();
        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
    }
    

    setInterval(() => {
        removeRealAds();
        handleYouTubeAds();
    }, 5000);
    
})();
