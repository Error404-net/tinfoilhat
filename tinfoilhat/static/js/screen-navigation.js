/* A deterministic exit from a standalone kiosk, even without browser history. */
document.addEventListener('keydown', (event) => {
    if (event.defaultPrevented || event.isComposing || event.ctrlKey || event.metaKey || event.shiftKey) return;
    const focused = document.activeElement;
    if (focused && (focused.isContentEditable || focused.closest('input, textarea, select'))) return;
    const goBack = (event.altKey && event.key === 'ArrowLeft') || (!event.altKey && event.key === 'Backspace');
    const backButton = document.getElementById('back-to-admin');
    if (goBack && backButton) {
        event.preventDefault();
        window.location.assign(backButton.href);
    }
});
