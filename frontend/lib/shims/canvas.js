"use strict";

/**
 * Build-time shim for pdfjs-dist's optional Node.js canvas dependency.
 *
 * In browser bundles this module should never be executed. If it is executed,
 * fail loudly with a clear error message.
 */
module.exports = {
    createCanvas() {
        throw new Error("The optional 'canvas' module is not available in this runtime.");
    },
};
