/* KEYSTROKE QUEST - keyboard.js
 * window.KQKeyboard : the on-screen QWERTY guide plus the two pixel hands.
 */
(function () {
  'use strict';

  var NUMBER_ROW = ['`', '1', '2', '3', '4', '5', '6', '7', '8', '9', '0', '-', '='];
  var TOP_ROW = ['q', 'w', 'e', 'r', 't', 'y', 'u', 'i', 'o', 'p', '[', ']', '\\'];
  var HOME_ROW = ['a', 's', 'd', 'f', 'g', 'h', 'j', 'k', 'l', ';', "'"];
  var BOTTOM_ROW = ['z', 'x', 'c', 'v', 'b', 'n', 'm', ',', '.', '/'];

  // A capital is typed with the OPPOSITE hand's shift, so we need the base key.
  var SHIFTED = {
    '~': '`', '!': '1', '@': '2', '#': '3', $: '4', '%': '5', '^': '6',
    '&': '7', '*': '8', '(': '9', ')': '0', _: '-', '+': '=',
    '{': '[', '}': ']', '|': '\\', ':': ';', '"': "'", '<': ',', '>': '.', '?': '/'
  };

  // Fallback used whenever the API finger_map has no entry for a key.
  var DEFAULT_FINGERS = {};
  (function seed() {
    function set(keys, hand, finger) {
      for (var i = 0; i < keys.length; i++) DEFAULT_FINGERS[keys[i]] = { hand: hand, finger: finger };
    }
    set(['`', '1', 'q', 'a', 'z'], 'left', 'pinky');
    set(['2', 'w', 's', 'x'], 'left', 'ring');
    set(['3', 'e', 'd', 'c'], 'left', 'middle');
    set(['4', '5', 'r', 't', 'f', 'g', 'v', 'b'], 'left', 'index');
    set(['6', '7', 'y', 'u', 'h', 'j', 'n', 'm'], 'right', 'index');
    set(['8', 'i', 'k', ','], 'right', 'middle');
    set(['9', 'o', 'l', '.'], 'right', 'ring');
    set(['0', '-', '=', 'p', '[', ']', '\\', ';', "'", '/'], 'right', 'pinky');
    set([' '], 'right', 'thumb');
  })();

  var FINGERS = ['pinky', 'ring', 'middle', 'index', 'thumb'];

  var fingerMap = {};
  var keyEls = {};            // 'f' -> element
  var shiftEls = {};          // 'left' | 'right' -> element
  var fingerEls = {};         // 'left:index' -> element
  var flashTimers = [];
  var highlighted = [];

  function el(id) {
    try {
      return document.getElementById(id);
    } catch (e) {
      return null;
    }
  }

  function label(key) {
    if (key === ' ') return 'SPACE';
    if (key === '\\') return '\\';
    return key.toUpperCase();
  }

  function fingerFor(key) {
    var info = fingerMap && fingerMap[key];
    if (info && info.hand && info.finger) return { hand: info.hand, finger: info.finger };
    var fallback = DEFAULT_FINGERS[key];
    if (fallback) return fallback;
    return { hand: 'right', finger: 'index' };
  }

  function makeKey(doc, key, extraClass, handOverride, fingerOverride) {
    var node = doc.createElement('div');
    var info = fingerFor(key);
    node.className = 'kq-key' + (extraClass ? ' ' + extraClass : '');
    node.setAttribute('data-key', key);
    node.setAttribute('data-finger', fingerOverride || info.finger);
    node.setAttribute('data-hand', handOverride || info.hand);
    node.textContent = label(key);
    return node;
  }

  function makeRow(doc, cls) {
    var row = doc.createElement('div');
    row.className = 'kq-key-row' + (cls ? ' ' + cls : '');
    return row;
  }

  /* --------------------------------------------------------------- mount */

  function mount(apiFingerMap) {
    try {
      if (apiFingerMap && typeof apiFingerMap === 'object') fingerMap = apiFingerMap;

      var board = el('kq-keyboard');
      var hands = el('kq-hands');
      keyEls = {};
      shiftEls = {};
      fingerEls = {};

      if (board) {
        var doc = board.ownerDocument || document;
        board.innerHTML = '';

        var rows = [NUMBER_ROW, TOP_ROW, HOME_ROW];
        for (var r = 0; r < rows.length; r++) {
          var row = makeRow(doc, 'kq-key-row--' + r);
          for (var i = 0; i < rows[r].length; i++) {
            var k = makeKey(doc, rows[r][i]);
            keyEls[rows[r][i]] = k;
            row.appendChild(k);
          }
          board.appendChild(row);
        }

        // bottom row is bracketed by the two shift keys
        var bottom = makeRow(doc, 'kq-key-row--3');
        var lshift = makeKey(doc, 'shift', 'kq-key--shift kq-key--wide', 'left', 'pinky');
        lshift.textContent = 'SHIFT';
        shiftEls.left = lshift;
        bottom.appendChild(lshift);
        for (var b = 0; b < BOTTOM_ROW.length; b++) {
          var bk = makeKey(doc, BOTTOM_ROW[b]);
          keyEls[BOTTOM_ROW[b]] = bk;
          bottom.appendChild(bk);
        }
        var rshift = makeKey(doc, 'shift', 'kq-key--shift kq-key--wide', 'right', 'pinky');
        rshift.textContent = 'SHIFT';
        shiftEls.right = rshift;
        bottom.appendChild(rshift);
        board.appendChild(bottom);

        var spaceRow = makeRow(doc, 'kq-key-row--space');
        var space = makeKey(doc, ' ', 'kq-key--space kq-key--wide');
        keyEls[' '] = space;
        spaceRow.appendChild(space);
        board.appendChild(spaceRow);
      }

      if (hands) {
        var hdoc = hands.ownerDocument || document;
        hands.innerHTML = '';
        var order = ['left', 'right'];
        for (var h = 0; h < order.length; h++) {
          var hand = order[h];
          var wrap = hdoc.createElement('div');
          wrap.className = 'kq-hand';
          wrap.setAttribute('data-hand', hand);
          // mirror the right hand so thumbs meet in the middle
          var seq = hand === 'left' ? FINGERS.slice() : FINGERS.slice().reverse();
          for (var f = 0; f < seq.length; f++) {
            var fingerEl = hdoc.createElement('div');
            fingerEl.className = 'kq-finger';
            fingerEl.setAttribute('data-hand', hand);
            fingerEl.setAttribute('data-finger', seq[f]);
            fingerEls[hand + ':' + seq[f]] = fingerEl;
            wrap.appendChild(fingerEl);
          }
          hands.appendChild(wrap);
        }
      }
    } catch (e) {
      /* a broken guide must never stop the typing loop */
    }
  }

  /* ----------------------------------------------------------- highlight */

  function resolve(ch) {
    if (ch == null || ch === '') return null;
    var c = String(ch);
    if (c === ' ' || c === '\u00a0' || c === '\n' || c === '\t') {
      return { key: ' ', shiftHand: null };
    }
    var base = SHIFTED[c];
    var needsShift = false;
    if (base) {
      needsShift = true;
    } else if (c.toLowerCase() !== c) {
      base = c.toLowerCase();
      needsShift = true;
    } else {
      base = c;
    }
    var shiftHand = null;
    if (needsShift) {
      shiftHand = fingerFor(base).hand === 'left' ? 'right' : 'left';
    }
    return { key: base, shiftHand: shiftHand };
  }

  function clearHighlights() {
    for (var i = 0; i < highlighted.length; i++) {
      var entry = highlighted[i];
      try {
        entry.el.classList.remove(entry.cls);
      } catch (e) {}
    }
    highlighted = [];
  }

  function mark(node, cls) {
    if (!node) return;
    try {
      node.classList.add(cls);
      highlighted.push({ el: node, cls: cls });
    } catch (e) {}
  }

  function highlight(ch) {
    try {
      clearHighlights();
      var target = resolve(ch);
      if (!target) return;

      mark(keyEls[target.key], 'kq-key--next');

      var info = fingerFor(target.key);
      mark(fingerEls[info.hand + ':' + info.finger], 'kq-finger--active');

      if (target.shiftHand) {
        mark(shiftEls[target.shiftHand], 'kq-key--next');
        mark(fingerEls[target.shiftHand + ':pinky'], 'kq-finger--active');
      }
    } catch (e) {}
  }

  function flash(ch, ok) {
    try {
      var target = resolve(ch);
      if (!target) return;
      var node = keyEls[target.key];
      if (!node) return;
      var cls = ok ? 'kq-key--hit' : 'kq-key--miss';
      node.classList.add(cls);
      var timer = setTimeout(function () {
        try {
          node.classList.remove(cls);
        } catch (e) {}
        var at = flashTimers.indexOf(timer);
        if (at !== -1) flashTimers.splice(at, 1);
      }, 120);
      flashTimers.push(timer);
    } catch (e) {}
  }

  function reset() {
    try {
      clearHighlights();
      for (var i = 0; i < flashTimers.length; i++) clearTimeout(flashTimers[i]);
      flashTimers = [];
      var stateClasses = ['kq-key--next', 'kq-key--hit', 'kq-key--miss'];
      var board = el('kq-keyboard');
      if (board) {
        var keys = board.querySelectorAll('.kq-key');
        for (var k = 0; k < keys.length; k++) {
          for (var c = 0; c < stateClasses.length; c++) keys[k].classList.remove(stateClasses[c]);
        }
      }
      var hands = el('kq-hands');
      if (hands) {
        var fingers = hands.querySelectorAll('.kq-finger');
        for (var f = 0; f < fingers.length; f++) fingers[f].classList.remove('kq-finger--active');
      }
    } catch (e) {}
  }

  window.KQKeyboard = {
    mount: mount,
    highlight: highlight,
    flash: flash,
    reset: reset,
    fingerFor: fingerFor
  };
})();
