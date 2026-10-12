async function loadDiagnostics(checkDevice = false) {
    const message = document.getElementById('diagnostics-message');
    const buttons = ['diagnostics-refresh', 'diagnostics-check'].map(id => document.getElementById(id));
    buttons.forEach(button => { button.disabled = true; });
    message.textContent = checkDevice ? 'Checking HackRF…' : 'Loading diagnostics…';
    try {
        if (checkDevice) {
            const check = await fetch('/admin/diagnostics/hackrf', { method: 'POST' });
            if (!check.ok) {
                const error = await check.json();
                throw new Error(error.error || 'The device check failed.');
            }
        }
        const response = await fetch('/admin/diagnostics', { cache: 'no-store' });
        if (!response.ok) throw new Error('Unable to load diagnostics.');
        const data = await response.json();
        const status = document.getElementById('diagnostics-status');
        status.replaceChildren();
        const lines = [`Python ${data.python} · ${data.platform}`];
        data.dependencies.forEach(item => lines.push(`${item.name}: ${item.available ? item.version : 'MISSING — reinstall the application'}`));
        Object.entries(data.tools).forEach(([name, path]) => lines.push(`${name}: ${path || 'MISSING — reinstall the application or install HackRF tools'}`));
        lines.forEach(line => {
            const paragraph = document.createElement('p');
            paragraph.textContent = line;
            status.appendChild(paragraph);
        });
        document.getElementById('diagnostics-device').textContent = data.hackrf
            ? `${data.hackrf.message} ${data.hackrf.advice} Checked: ${new Date(data.hackrf.checked_at).toLocaleString()}`
            : 'No check has been run yet. Click Check HackRF to test the connection.';
        document.getElementById('diagnostics-output').textContent = data.hackrf?.output || '';
        document.getElementById('diagnostics-log-path').textContent = data.log_path
            ? `Log file: ${data.log_path} (showing the most recent 64 KB)`
            : 'Showing recent logs from this application session.';
        document.getElementById('diagnostics-logs').textContent = data.logs || 'No logs recorded yet.';
        message.textContent = 'Diagnostics updated.';
    } catch (error) {
        message.textContent = error.message;
    } finally {
        buttons.forEach(button => { button.disabled = false; });
    }
}
document.getElementById('diagnostics-refresh').addEventListener('click', () => loadDiagnostics());
document.getElementById('diagnostics-check').addEventListener('click', () => loadDiagnostics(true));
