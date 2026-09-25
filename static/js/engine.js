/* KEYSTROKE QUEST - engine.js
 * window.TypingEngine : the typing surface. Owns the text DOM, the caret,
 * the cursor index, the keystroke log and the WPM maths. Knows nothing about
 * hearts, combos or bosses - that is game.js.
 */
(function () {
  'use strict';

  var NBSP = '\u00a0';
  var PROGRESS_MS = 250;

  function noop() {}

  function now() {
    try {
      return window.performance && window.performance.now ? window.performance.now() : Date.now();
    } catch (e) {
      return Date.now();
    }
  }

  function reducedMotion() {
    try {
      if (window.KQ_SETTINGS && window.KQ_SETTINGS.reduced_motion) return true;
      return !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
    } catch (e) {
      return false;
    }
  }

  var TypingEngine = function (options) {
    var opts = options || {};
    this.textEl = opts.textEl || null;
    this.caretEl = opts.caretEl || null;
    this.inputEl = opts.inputEl || null;
    this.lines = Array.isArray(opts.lines) ? opts.lines.slice() : [];

    this.onKey = typeof opts.onKey === 'function' ? opts.onKey : noop;
    this.onProgress = typeof opts.onProgress === 'function' ? opts.onProgress : noop;
    this.onComplete = typeof opts.onComplete === 'function' ? opts.onComplete : noop;

    this.text = this.lines
      .map(function (line) {
        return String(line == null ? '' : line).replace(/\s+/g, ' ').trim();
      })
      .filter(function (line) {
        return line.length > 0;
      })
      .join(' ');

    this.chars = [];
    this.index = 0;
    this.keystrokes = [];
    this.correctCount = 0;
    this.typedCount = 0;
    this.errorCount = 0;
    this.startTime = null;
    this.lastTime = null;
    this.endTime = null;
    this.finished = false;
    this.running = false;

    this._listeners = [];
    this._interval = null;
    this._raf = null;
    this._blurTimer = null;
    this._lastScrollTop = null;
    this._caretOrigin = null;

    this._render();
  };

  /* ---------------------------------------------------------------- build */

  TypingEngine.prototype._render = function () {
    this.chars = [];
    if (!this.textEl) return;
    var doc = this.textEl.ownerDocument || document;
    this.textEl.innerHTML = '';
    if (!this.text) return;

    var words = this.text.split(' ');
    var frag = doc.createDocumentFragment();

    for (var w = 0; w < words.length; w++) {
      var wordEl = doc.createElement('span');
      wordEl.className = 'kq-word';
      var word = words[w];
      for (var i = 0; i < word.length; i++) {
        wordEl.appendChild(this._charSpan(doc, word.charAt(i)));
      }
      // the separating space lives inside the word it follows so it never wraps alone
      if (w < words.length - 1) {
        wordEl.appendChild(this._charSpan(doc, ' '));
      }
      frag.appendChild(wordEl);
      // the space spans hold a non-breaking space for width, so give the browser
      // an explicit (zero-width) break opportunity between words instead
      if (w < words.length - 1) {
        frag.appendChild(doc.createElement('wbr'));
      }
    }
    this.textEl.appendChild(frag);
    this._paintCurrent();
  };

  TypingEngine.prototype._charSpan = function (doc, ch) {
    var span = doc.createElement('span');
    span.className = 'kq-char';
    span.setAttribute('data-char', ch);
    span.textContent = ch === ' ' ? NBSP : ch;
    this.chars.push({ el: span, ch: ch, typed: null, correct: null });
    return span;
  };

  /* ------------------------------------------------------------ lifecycle */

  TypingEngine.prototype._on = function (target, type, handler, opts) {
    if (!target || !target.addEventListener) return;
    target.addEventListener(type, handler, opts);
    this._listeners.push({ target: target, type: type, handler: handler, opts: opts });
  };

  TypingEngine.prototype._offAll = function () {
    for (var i = 0; i < this._listeners.length; i++) {
      var l = this._listeners[i];
      try {
        l.target.removeEventListener(l.type, l.handler, l.opts);
      } catch (e) {}
    }
    this._listeners = [];
  };

  TypingEngine.prototype._clearTimers = function () {
    if (this._interval) {
      clearInterval(this._interval);
      this._interval = null;
    }
    if (this._raf) {
      try {
        cancelAnimationFrame(this._raf);
      } catch (e) {}
      this._raf = null;
    }
    if (this._blurTimer) {
      clearTimeout(this._blurTimer);
      this._blurTimer = null;
    }
  };

  TypingEngine.prototype.start = function () {
    var self = this;
    this._offAll();
    this._clearTimers();
    this.running = true;

    if (this.inputEl) {
      try {
        this.inputEl.value = '';
        this.inputEl.setAttribute('autocomplete', 'off');
        this.inputEl.setAttribute('autocapitalize', 'off');
        this.inputEl.setAttribute('autocorrect', 'off');
        this.inputEl.setAttribute('spellcheck', 'false');
      } catch (e) {}

      this._on(this.inputEl, 'keydown', function (ev) {
        self._onKeyDown(ev);
      });
      // covers mobile keyboards and IME commits, which produce no usable keydown
      this._on(this.inputEl, 'input', function () {
        self._onInput();
      });
      this._on(this.inputEl, 'blur', function () {
        self._scheduleRefocus();
      });
    }

    var refocus = function () {
      self.focus();
    };
    if (this.textEl) this._on(this.textEl, 'mousedown', refocus);
    if (this.textEl) this._on(this.textEl, 'click', refocus);
    if (this.textEl && this.textEl.parentElement) {
      this._on(this.textEl.parentElement, 'click', refocus);
    }
    this._on(window, 'focus', refocus);

    this._on(window, 'resize', function () {
      self._caretOrigin = null; // wrapping (and the caret origin) can change
      self._lastScrollTop = null;
      self._scheduleReflow();
    });

    this._interval = setInterval(function () {
      self._emitProgress();
    }, PROGRESS_MS);

    this.focus();
    this._scheduleReflow();
    this._emitProgress();
    return this;
  };

  TypingEngine.prototype.reset = function () {
    this._offAll();
    this._clearTimers();
    this.index = 0;
    this.keystrokes = [];
    this.correctCount = 0;
    this.typedCount = 0;
    this.errorCount = 0;
    this.startTime = null;
    this.lastTime = null;
    this.endTime = null;
    this.finished = false;
    this._lastScrollTop = null;
    this._caretOrigin = null;
    this._render();
    var container = this._scrollContainer();
    if (container) {
      try {
        container.scrollTop = 0;
      } catch (e) {}
    }
    this.start();
    return this;
  };

  TypingEngine.prototype.destroy = function () {
    this.running = false;
    this._offAll();
    this._clearTimers();
    return this;
  };

  /* ---------------------------------------------------------------- focus */

  TypingEngine.prototype.focus = function () {
    if (!this.inputEl || !this.running || this.finished) return;
    try {
      if (document.activeElement !== this.inputEl) {
        this.inputEl.focus({ preventScroll: true });
      }
    } catch (e) {
      try {
        this.inputEl.focus();
      } catch (e2) {}
    }
  };

  TypingEngine.prototype._scheduleRefocus = function () {
    var self = this;
    if (this._blurTimer) clearTimeout(this._blurTimer);
    this._blurTimer = setTimeout(function () {
      self._blurTimer = null;
      if (!self.running || self.finished) return;
      try {
        if (window.KQDialogue && window.KQDialogue.isOpen()) return;
        var active = document.activeElement;
        var tag = active && active.tagName ? active.tagName.toUpperCase() : '';
        // do not steal focus from buttons / overlays the player is using
        if (tag === 'BUTTON' || tag === 'A' || tag === 'SELECT' || tag === 'TEXTAREA') return;
        if (active && active !== document.body && active !== self.inputEl && tag === 'INPUT') return;
      } catch (e) {}
      self.focus();
    }, 40);
  };

  /* ---------------------------------------------------------------- input */

  TypingEngine.prototype._onKeyDown = function (ev) {
    if (!this.running || this.finished) return;
    try {
      if (window.KQDialogue && window.KQDialogue.isOpen()) return;
    } catch (e) {}

    var key = ev.key;
    if (key === 'Backspace') {
      ev.preventDefault();
      this._backspace();
      return;
    }
    if (ev.ctrlKey || ev.metaKey || ev.altKey) return;
    if (typeof key !== 'string') return;
    // Enter, Tab, Escape and the arrows are left alone for game.js shortcuts
    if (key.length !== 1) return;
    ev.preventDefault();
    this._type(key);
  };

  TypingEngine.prototype._onInput = function () {
    if (!this.inputEl) return;
    var value = this.inputEl.value;
    if (!value) return;
    this.inputEl.value = '';
    if (!this.running || this.finished) return;
    for (var i = 0; i < value.length; i++) {
      this._type(value.charAt(i));
    }
  };

  TypingEngine.prototype._type = function (rawChar) {
    if (!this.running || this.finished) return;
    if (this.index >= this.chars.length) return;

    var ch = rawChar === NBSP ? ' ' : rawChar;
    var stamp = now();
    if (this.startTime == null) {
      this.startTime = stamp; // the clock starts on the FIRST keystroke
      this.lastTime = stamp;
    }
    var ms = Math.max(0, Math.round(stamp - (this.lastTime == null ? stamp : this.lastTime)));
    this.lastTime = stamp;

    var entry = this.chars[this.index];
    var expected = entry.ch;
    var correct = ch === expected;
    var typedIndex = this.index;

    entry.typed = ch;
    entry.correct = correct;
    try {
      entry.el.classList.remove('kq-char--current');
      entry.el.classList.remove(correct ? 'kq-char--wrong' : 'kq-char--correct');
      entry.el.classList.add(correct ? 'kq-char--correct' : 'kq-char--wrong');
    } catch (e) {}

    this.typedCount += 1;
    if (correct) this.correctCount += 1;
    else this.errorCount += 1;
    this.keystrokes.push({ expected: expected, typed: ch, ms: ms });

    this.index += 1;
    this._paintCurrent();
    this._reflow();

    try {
      this.onKey({
        expected: expected,
        typed: ch,
        correct: correct,
        ms: ms,
        index: typedIndex
      });
    } catch (e) {}

    if (this.index >= this.chars.length) this._finish();
  };

  TypingEngine.prototype._backspace = function () {
    if (this.index <= 0) return;
    var prev = this.chars[this.index - 1];
    // only back to the start of the current word (a correctly typed space is a wall)
    if (prev.ch === ' ' && prev.correct === true) return;

    this._clearCharState(this.chars[this.index]);
    this.index -= 1;
    prev.typed = null;
    prev.correct = null;
    this._clearCharState(prev);
    this._paintCurrent();
    this._reflow();
  };

  TypingEngine.prototype._clearCharState = function (entry) {
    if (!entry || !entry.el) return;
    try {
      entry.el.classList.remove('kq-char--correct');
      entry.el.classList.remove('kq-char--wrong');
      entry.el.classList.remove('kq-char--extra');
    } catch (e) {}
  };

  TypingEngine.prototype._paintCurrent = function () {
    if (!this.textEl) return;
    try {
      var marked = this.textEl.querySelectorAll('.kq-char--current');
      for (var i = 0; i < marked.length; i++) marked[i].classList.remove('kq-char--current');
      var entry = this.chars[this.index];
      if (entry && entry.el) entry.el.classList.add('kq-char--current');
    } catch (e) {}
  };

  /* ------------------------------------------------------- caret + scroll */

  TypingEngine.prototype._scheduleReflow = function () {
    var self = this;
    if (this._raf) return;
    try {
      this._raf = requestAnimationFrame(function () {
        self._raf = null;
        self._reflow();
      });
    } catch (e) {
      this._raf = null;
      this._reflow();
    }
  };

  TypingEngine.prototype._reflow = function () {
    this._moveCaret();
    this._scrollToCurrent();
  };

  TypingEngine.prototype._currentEl = function () {
    var entry = this.chars[this.index];
    if (entry) return { el: entry.el, after: false };
    var last = this.chars[this.chars.length - 1];
    if (last) return { el: last.el, after: true };
    return null;
  };

  TypingEngine.prototype.getCaretPos = function () {
    var target = this._currentEl();
    if (!target || !target.el) return null;
    var host = (this.caretEl && this.caretEl.offsetParent) || this.textEl;
    if (!host || !host.getBoundingClientRect) return null;
    try {
      var hostRect = host.getBoundingClientRect();
      var rect = target.el.getBoundingClientRect();
      return {
        x: rect.left - hostRect.left + host.scrollLeft + (target.after ? rect.width : 0),
        y: rect.top - hostRect.top + host.scrollTop,
        height: rect.height,
        width: rect.width,
        clientX: rect.left + (target.after ? rect.width : 0),
        clientY: rect.top
      };
    } catch (e) {
      return null;
    }
  };

  // Where the caret sits with no transform applied, so translate() offsets are
  // correct even if the stylesheet does not anchor it at the container origin.
  TypingEngine.prototype._measureCaretOrigin = function () {
    this._caretOrigin = { x: 0, y: 0 };
    if (!this.caretEl) return;
    try {
      this.caretEl.style.transform = 'translate(0px, 0px)';
      var host = this.caretEl.offsetParent || this.textEl;
      if (!host || !host.getBoundingClientRect) return;
      var hostRect = host.getBoundingClientRect();
      var rect = this.caretEl.getBoundingClientRect();
      this._caretOrigin = {
        x: rect.left - hostRect.left + host.scrollLeft,
        y: rect.top - hostRect.top + host.scrollTop
      };
    } catch (e) {}
  };

  TypingEngine.prototype._moveCaret = function () {
    if (!this.caretEl) return;
    var pos = this.getCaretPos();
    if (!pos) return;
    if (!this._caretOrigin) this._measureCaretOrigin();
    var origin = this._caretOrigin || { x: 0, y: 0 };
    try {
      this.caretEl.style.transform =
        'translate(' + Math.round(pos.x - origin.x) + 'px, ' + Math.round(pos.y - origin.y) + 'px)';
      if (pos.height) this.caretEl.style.height = Math.round(pos.height) + 'px';
    } catch (e) {}
  };

  TypingEngine.prototype._scrollContainer = function () {
    var node = this.textEl;
    try {
      while (node && node !== document.body && node !== document.documentElement) {
        var style = window.getComputedStyle(node);
        var oy = style ? style.overflowY : '';
        if (
          (oy === 'auto' || oy === 'scroll' || oy === 'hidden') &&
          node.scrollHeight > node.clientHeight + 2
        ) {
          return node;
        }
        node = node.parentElement;
      }
    } catch (e) {}
    return null;
  };

  TypingEngine.prototype._scrollToCurrent = function () {
    var container = this._scrollContainer();
    if (!container) return;
    var target = this._currentEl();
    if (!target || !target.el) return;
    try {
      var cRect = container.getBoundingClientRect();
      var rect = target.el.getBoundingClientRect();
      var delta = rect.top - cRect.top - (container.clientHeight - rect.height) / 2;
      var next = Math.max(0, Math.min(container.scrollHeight, container.scrollTop + delta));
      if (this._lastScrollTop != null && Math.abs(next - this._lastScrollTop) < 2) return;
      this._lastScrollTop = next;
      if (!reducedMotion() && typeof container.scrollTo === 'function') {
        container.scrollTo({ top: next, behavior: 'smooth' });
      } else {
        container.scrollTop = next;
      }
    } catch (e) {}
  };

  /* ---------------------------------------------------------------- stats */

  TypingEngine.prototype.getStats = function () {
    var elapsed = 0;
    if (this.startTime != null) {
      elapsed = Math.max(0, (this.endTime == null ? now() : this.endTime) - this.startTime);
    }
    var minutes = elapsed / 60000;
    var wpm = minutes > 0 ? this.correctCount / 5 / minutes : 0;
    var rawWpm = minutes > 0 ? this.typedCount / 5 / minutes : 0;
    var accuracy = this.typedCount > 0 ? this.correctCount / this.typedCount : 1;
    return {
      wpm: Math.max(0, Math.round(wpm * 10) / 10),
      rawWpm: Math.max(0, Math.round(rawWpm * 10) / 10),
      accuracy: Math.max(0, Math.min(1, Math.round(accuracy * 1000) / 1000)),
      elapsedMs: Math.round(elapsed),
      durationMs: Math.round(elapsed),
      index: this.index,
      total: this.chars.length,
      correct: this.correctCount,
      typed: this.typedCount,
      errors: this.errorCount,
      keystrokes: this.keystrokes.slice()
    };
  };

  TypingEngine.prototype._emitProgress = function () {
    var stats = this.getStats();
    try {
      this.onProgress({
        wpm: stats.wpm,
        rawWpm: stats.rawWpm,
        accuracy: stats.accuracy,
        elapsedMs: stats.elapsedMs,
        index: stats.index,
        total: stats.total
      });
    } catch (e) {}
  };

  TypingEngine.prototype._finish = function () {
    if (this.finished) return;
    this.finished = true;
    this.endTime = now();
    this._clearTimers();
    this.running = false;
    var stats = this.getStats();
    this._emitProgress();
    try {
      this.onComplete(stats);
    } catch (e) {}
  };

  // let game.js end a run early (boss killed, hearts gone)
  TypingEngine.prototype.stop = function () {
    this.finished = true;
    this.endTime = this.endTime == null ? now() : this.endTime;
    this.running = false;
    this._offAll();
    this._clearTimers();
    return this.getStats();
  };

  TypingEngine.prototype.expectedChar = function () {
    var entry = this.chars[this.index];
    return entry ? entry.ch : null;
  };

  window.TypingEngine = TypingEngine;
})();
