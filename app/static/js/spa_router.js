document.addEventListener('DOMContentLoaded', () => {
    
    // Inject the top loading bar into the body
    const loader = document.createElement('div');
    loader.id = 'spa-loader';
    document.body.appendChild(loader);

    // Track loaded scripts and styles to avoid duplicates
    const loadedScripts = new Set(Array.from(document.querySelectorAll('script[src]')).map(s => s.src));
    const loadedStyles = new Set(Array.from(document.querySelectorAll('link[rel="stylesheet"]')).map(l => l.href));

    function executeScript(scriptElement) {
        return new Promise((resolve) => {
            const newScript = document.createElement('script');
            Array.from(scriptElement.attributes).forEach(attr => newScript.setAttribute(attr.name, attr.value));
            
            if (scriptElement.src) {
                if (loadedScripts.has(scriptElement.src)) {
                    resolve(); // Already loaded
                    return;
                }
                newScript.onload = resolve;
                newScript.onerror = resolve; // Continue even if error
                loadedScripts.add(scriptElement.src);
            } else {
                newScript.appendChild(document.createTextNode(scriptElement.innerHTML));
                resolve();
            }
            
            document.body.appendChild(newScript);
        });
    }

    async function loadAssets(doc) {
        // Load CSS
        const newStyles = Array.from(doc.querySelectorAll('link[rel="stylesheet"]'));
        newStyles.forEach(style => {
            if (style.href && !loadedStyles.has(style.href)) {
                const newLink = document.createElement('link');
                newLink.rel = 'stylesheet';
                newLink.href = style.href;
                document.head.appendChild(newLink);
                loadedStyles.add(style.href);
            }
        });

        // Load JS (sequentially to respect dependencies)
        const allScripts = Array.from(doc.querySelectorAll('script'));
        for (const script of allScripts) {
            // Only execute if it's not the router itself
            if (!script.src || !script.src.includes('spa_router.js')) {
                await executeScript(script);
            }
        }
    }

    // Function to load a new page asynchronously
    async function navigateTo(url, pushState = true) {
        try {
            // Trigger cleanup events (so hub.js/dashboard.js can close EventSources, Intervals, etc.)
            const cleanupEvent = new CustomEvent('before-spa-navigate', { detail: { url } });
            window.dispatchEvent(cleanupEvent);

            loader.style.width = '50%';
            loader.style.opacity = '1';

            const response = await fetch(url);
            
            // If the server redirected us (e.g. to /login because of auth), do a hard redirect
            if (response.redirected) {
                window.location.href = response.url;
                return;
            }

            if (!response.ok) {
                throw new Error('Network error');
            }
            
            const htmlText = await response.text();
            
            // Parse the incoming HTML
            const parser = new DOMParser();
            const doc = parser.parseFromString(htmlText, 'text/html');
            
            // Extract the new main content and title
            const newContent = doc.querySelector('.main-content');
            const newTitle = doc.title;
            
            if (newContent) {
                // Update DOM
                const currentContent = document.querySelector('.main-content');
                if (currentContent) {
                    currentContent.innerHTML = newContent.innerHTML;
                    
                    // Load Head CSS and Body JS
                    await loadAssets(doc);
                }
                
                document.title = newTitle;
                
                // Update Sidebar Active State
                document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
                
                // Normalize URL for matching sidebar
                const normalize = (u) => {
                    let path = new URL(u, window.location.origin).pathname;
                    if (path.endsWith('/') && path.length > 1) path = path.slice(0, -1);
                    return path;
                };
                
                const currentPath = normalize(url);
                document.querySelectorAll('.nav-item').forEach(el => {
                    const href = el.getAttribute('href');
                    if (href && normalize(href) === currentPath) {
                        el.classList.add('active');
                    }
                });

                // Update Browser History
                if (pushState) {
                    window.history.pushState({ path: url }, newTitle, url);
                }
                
                // Trigger page-loaded event for page-specific scripts to initialize
                const loadedEvent = new CustomEvent('spa-page-loaded', { detail: { url } });
                window.dispatchEvent(loadedEvent);
                
                // Finish loader
                loader.style.width = '100%';
                setTimeout(() => {
                    loader.style.opacity = '0';
                    setTimeout(() => { loader.style.width = '0%'; }, 300);
                }, 300);
            } else {
                // Fallback to normal navigation if structure isn't exactly as expected
                window.location.href = url;
            }
        } catch (error) {
            console.error('SPA Navigation failed:', error);
            window.location.href = url; // Fallback to hard reload
        }
    }

    // Intercept Sidebar Clicks
    document.addEventListener('click', (e) => {
        // Find closest anchor tag
        const link = e.target.closest('a');
        if (!link) return;
        
        const url = link.getAttribute('href');
        
        // Only intercept internal GET navigation links
        if (url && url.startsWith('/') && !url.startsWith('javascript') && !url.includes('logout') && !url.includes('login')) {
            // Only trigger SPA if they clicked a nav-item or primary button, or any internal link within main content
            if (link.classList.contains('nav-item') || link.closest('.main-content')) {
                // Allow target="_blank" to open normally
                if (link.getAttribute('target') === '_blank') return;
                
                e.preventDefault();
                
                // Don't reload if we are already there
                if (window.location.pathname + window.location.search !== url) {
                    navigateTo(url);
                }
            }
        }
    });

    // Handle Browser Back/Forward Buttons
    window.addEventListener('popstate', (e) => {
        if (e.state && e.state.path) {
            navigateTo(e.state.path, false);
        } else {
            window.location.reload();
        }
    });

    // Initialize initial state
    window.history.replaceState({ path: window.location.pathname + window.location.search }, document.title, window.location.pathname + window.location.search);
});
