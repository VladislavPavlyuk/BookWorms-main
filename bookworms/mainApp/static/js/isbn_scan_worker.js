/* ISBN decode worker — same-origin ZXing via Django (not /static volume). */
/* global ZXing, importScripts */
importScripts("/library/isbn-scan-assets/zxing-0.21.3.min.js");

var hints = new Map();
hints.set(ZXing.DecodeHintType.POSSIBLE_FORMATS, [
    ZXing.BarcodeFormat.EAN_13,
    ZXing.BarcodeFormat.EAN_8,
    ZXing.BarcodeFormat.UPC_A,
    ZXing.BarcodeFormat.UPC_E,
]);
hints.set(ZXing.DecodeHintType.TRY_HARDER, true);

var reader = new ZXing.MultiFormatReader();
reader.setHints(hints);

function toGrey(rgba, w, h) {
    var out = new Uint8ClampedArray(w * h);
    for (var i = 0, j = 0; i < out.length; i++, j += 4) {
        out[i] = (rgba[j] * 306 + rgba[j + 1] * 601 + rgba[j + 2] * 117) >> 10;
    }
    return out;
}

function decodeGrey(grey, w, h) {
    var source = new ZXing.RGBLuminanceSource(grey, w, h);
    var bitmap = new ZXing.BinaryBitmap(new ZXing.HybridBinarizer(source));
    try {
        var result = reader.decodeWithState(bitmap);
        reader.reset();
        return result.getText();
    } catch (e) {
        reader.reset();
    }
    try {
        var inv = source.invert();
        var bitmap2 = new ZXing.BinaryBitmap(new ZXing.HybridBinarizer(inv));
        var result2 = reader.decodeWithState(bitmap2);
        reader.reset();
        return result2.getText();
    } catch (e2) {
        reader.reset();
    }
    return null;
}

self.onmessage = function (ev) {
    var msg = ev.data || {};
    var id = msg.id;
    try {
        var w = msg.width | 0;
        var h = msg.height | 0;
        var rgba = new Uint8ClampedArray(msg.buffer);
        var grey = toGrey(rgba, w, h);
        var text = decodeGrey(grey, w, h);
        self.postMessage({ id: id, text: text, ok: true });
    } catch (err) {
        try {
            reader.reset();
        } catch (e3) {}
        self.postMessage({
            id: id,
            text: null,
            ok: false,
            error: String(err && err.message ? err.message : err),
        });
    }
};
