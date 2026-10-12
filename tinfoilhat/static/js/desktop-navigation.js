/* Open presentation pages in native windows, retaining the Admin window. */
let displayFullscreen = false;
document.addEventListener('click', async event => {
    const link = event.target.closest('a[href]');
    if (!link || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    const url = new URL(link.href, location.href);
    if (url.origin !== location.origin || !['/billboard', '/design-billboard'].includes(url.pathname)) return;
    if (!window.pywebview?.api) return;
    event.preventDefault();
    try {
        await window.pywebview.api.open_display(url.pathname);
    } catch (error) {
        alert(`Unable to open the display window: ${error.message || error}`);
    }
});

async function toggleDisplayFullscreen() {
    if (!window.pywebview?.api) return;
    displayFullscreen = await window.pywebview.api.toggle_fullscreen();
    updateFullscreenButton();
}

function updateFullscreenButton() {
    const button = document.getElementById('display-fullscreen');
    if (button) {
        button.textContent = displayFullscreen ? 'Exit full screen' : 'Full screen';
        button.setAttribute('aria-pressed', String(displayFullscreen));
    }
}

window.addEventListener('pywebviewready', async () => {
    displayFullscreen = await window.pywebview.api.get_fullscreen();
    updateFullscreenButton();
});

document.addEventListener('click', event => {
    if (event.target.closest('#display-fullscreen')) toggleDisplayFullscreen();
});
document.addEventListener('keydown', event => {
    if (event.key === 'F11' || (event.key === 'Escape' && displayFullscreen)) {
        event.preventDefault();
        toggleDisplayFullscreen();
    }
});
