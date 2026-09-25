/* KEYSTROKE QUEST - title.js
 * Homepage music theme, poppable drifting clouds, DEMO button hook.
 */
(function () {
  'use strict';

  var MIN_CLOUDS = 3;
  var RESPAWN_MS = 3000;
  var SIZES = ['', 'kq-cloud--2', 'kq-cloud--3'];
  var layer = null;

  function audio(name, arg) {
    try {
      if (window.KQAudio && typeof window.KQAudio[name] === 'function') {
        window.KQAudio[name](arg);
      }
    } catch (e) {}
  }

  function startTitleMusic() {
    try {
      audio('bgmStart');
    } catch (e) {}
  }

  function spawnPuffs(x, y) {
    var n = 5 + Math.floor(Math.random() * 2);
    for (var i = 0; i < n; i++) {
      var puff = document.createElement('span');
      puff.className = 'kq-puff';
      var ang = (Math.PI * 2 * i) / n;
      var dist = 18 + Math.random() * 22;
      puff.style.left = x + Math.cos(ang) * dist + 'px';
      puff.style.top = y + Math.sin(ang) * dist + 'px';
      document.body.appendChild(puff);
      window.setTimeout(function (node) {
        return function () {
          try {
            if (node.parentNode) node.parentNode.removeChild(node);
          } catch (e) {}
        };
      }(puff), 420);
    }
  }

  function spawnCloud(fromLeft) {
    if (!layer) return;
    var wrap = document.createElement('div');
    wrap.className = 'kq-cloud-wrap';
    wrap.style.top = 8 + Math.random() * 52 + '%';
    wrap.style.animationDuration = 26 + Math.random() * 28 + 's';
    wrap.style.animationDelay = fromLeft ? '0s' : '-' + (8 + Math.random() * 20) + 's';

    var cloud = document.createElement('button');
    cloud.type = 'button';
    cloud.className = 'kq-cloud ' + SIZES[Math.floor(Math.random() * SIZES.length)];
    cloud.setAttribute('aria-label', 'Pop cloud');
    cloud.addEventListener('click', function (ev) {
      try {
        ev.preventDefault();
        ev.stopPropagation();
      } catch (e) {}
      popCloud(wrap, cloud);
    });

    wrap.appendChild(cloud);
    layer.appendChild(wrap);
  }

  function popCloud(wrap, cloud) {
    if (!wrap || wrap.getAttribute('data-popped') === 'true') return;
    wrap.setAttribute('data-popped', 'true');
    try {
      var box = cloud.getBoundingClientRect();
      spawnPuffs(box.left + box.width / 2, box.top + box.height / 2);
    } catch (e) {}
    audio('combo', 20);
    try {
      cloud.classList.add('kq-cloud--pop');
    } catch (e) {}
    window.setTimeout(function () {
      try {
        if (wrap.parentNode) wrap.parentNode.removeChild(wrap);
      } catch (e) {}
    }, 380);
    window.setTimeout(function () {
      spawnCloud(true);
      fillClouds();
    }, RESPAWN_MS);
  }

  function fillClouds() {
    if (!layer) return;
    var live = layer.querySelectorAll('.kq-cloud-wrap:not([data-popped="true"])').length;
    while (live < MIN_CLOUDS) {
      spawnCloud(false);
      live += 1;
    }
  }

  function bindDemo() {
    var btn = document.getElementById('kq-demo-btn');
    if (!btn) return;
    btn.addEventListener('click', function (ev) {
      try {
        ev.preventDefault();
      } catch (e) {}
      if (window.KQDemo && window.KQDemo.play) window.KQDemo.play();
    });
  }

  function boot() {
    layer = document.getElementById('kq-clouds');
    fillClouds();
    bindDemo();
    try {
      document.addEventListener('pointerdown', startTitleMusic, { passive: true, once: true });
    } catch (e) {}
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
