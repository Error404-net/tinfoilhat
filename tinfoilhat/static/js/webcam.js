class WebcamCapture {
    constructor({ videoEl, canvasEl, previewEl, fileInput, snapBtn, retakeBtn, webcamBtn, cancelBtn }) {
        this.video    = videoEl;
        this.canvas   = canvasEl;
        this.preview  = previewEl;
        this.file     = fileInput;
        this.snapBtn  = snapBtn;
        this.retakeBtn = retakeBtn;
        this.webcamBtn = webcamBtn;
        this.cancelBtn = cancelBtn;
        this._stream  = null;
        this._blob    = null;

        snapBtn.addEventListener('click',   () => this.snap());
        retakeBtn.addEventListener('click', () => this.retake());
        webcamBtn.addEventListener('click', () => this.start());
        cancelBtn.addEventListener('click', () => this.cancel());
    }

    async start() {
        try {
            this._stream = await navigator.mediaDevices.getUserMedia({ video: true });
            this.video.srcObject = this._stream;
            this.video.style.display = 'block';
            this.preview.style.display = 'none';
            this.snapBtn.style.display  = 'inline-block';
            this.retakeBtn.style.display = 'none';
            this.cancelBtn.style.display = 'inline-block';
            this.webcamBtn.style.display = 'none';
            this.file.style.display = 'none';
            this._blob = null;
        } catch (e) {
            alert('Camera access denied or unavailable.');
        }
    }

    snap() {
        const w = this.video.videoWidth, h = this.video.videoHeight;
        this.canvas.width = w; this.canvas.height = h;
        this.canvas.getContext('2d').drawImage(this.video, 0, 0, w, h);
        this.canvas.toBlob(blob => {
            this._blob = blob;
            this.preview.src = URL.createObjectURL(blob);
            this.video.style.display = 'none';
            this.preview.style.display = 'block';
            this.snapBtn.style.display  = 'none';
            this.retakeBtn.style.display = 'inline-block';
            this._stopStream();
        }, 'image/jpeg', 0.92);
    }

    retake() {
        this._blob = null;
        this.preview.style.display = 'none';
        this.retakeBtn.style.display = 'none';
        this.start();
    }

    cancel() {
        this._stopStream();
        this._blob = null;
        this.video.style.display = 'none';
        this.preview.style.display = 'none';
        this.snapBtn.style.display  = 'none';
        this.retakeBtn.style.display = 'none';
        this.cancelBtn.style.display = 'none';
        this.webcamBtn.style.display = 'inline-block';
        this.file.style.display = 'block';
    }

    getBlob() { return this._blob; }

    reset() {
        this.cancel();
        this.file.value = '';
    }

    _stopStream() {
        if (this._stream) {
            this._stream.getTracks().forEach(t => t.stop());
            this._stream = null;
        }
    }
}
