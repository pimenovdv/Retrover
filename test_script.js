// Mock canvas and event handling based exactly on app.js
let canvas = {
    isDrawingMode: true,
    freeDrawingBrush: {color: '#000000', width: 2},
    getActiveObject: () => null
};
let isEraserMode = false;
let isLassoMode = false;

// Mock prop elements
const listeners = {};
const mockElement = (id) => ({
    id,
    value: '',
    addEventListener: (type, cb) => {
        if (!listeners[id]) listeners[id] = {};
        if (!listeners[id][type]) listeners[id][type] = [];
        listeners[id][type].push(cb);
    },
    dispatchEvent: (e) => {
        if (listeners[id] && listeners[id][e.type]) {
            listeners[id][e.type].forEach(cb => cb({target: mockElement(id), ...e}));
        }
    }
});

const propStroke = mockElement('prop-stroke');
propStroke.value = '#000000';

const propStrokeWidth = mockElement('prop-stroke-width');
propStrokeWidth.value = '2';

// 1. Initial change listener
[propStroke, propStrokeWidth].forEach(input => {
    input.addEventListener('change', (e) => {
        const prop = e.target.id.replace('prop-', '');
        let val = e.target.value;

        if (prop === 'stroke-width') val = parseInt(val, 10);

        if (canvas.isDrawingMode && !isEraserMode && !isLassoMode) {
            if (prop === 'stroke') {
                canvas.freeDrawingBrush.color = val;
            } else if (prop === 'stroke-width') {
                canvas.freeDrawingBrush.width = val;
            }
        }

        const activeObject = canvas.getActiveObject();
        if (!activeObject) return;
        // ... (rest is skipped)
    });

    input.addEventListener('input', (e) => {
        const prop = e.target.id.replace('prop-', '');
        let val = e.target.value;
        if (prop === 'stroke-width') val = parseInt(val, 10);

        if (canvas.isDrawingMode && !isEraserMode && !isLassoMode) {
            if (prop === 'stroke') {
                canvas.freeDrawingBrush.color = val;
            } else if (prop === 'stroke-width') {
                canvas.freeDrawingBrush.width = val;
            }
        }
    });
});

// 2. Specific listeners
propStroke.addEventListener('input', (e) => {
     if (canvas.isDrawingMode && !isEraserMode && !isLassoMode) {
         canvas.freeDrawingBrush.color = e.target.value;
     }
});

propStroke.value = '#ff0000';
propStroke.dispatchEvent({type: 'input'});
console.log(canvas.freeDrawingBrush.color); // Expected #ff0000
