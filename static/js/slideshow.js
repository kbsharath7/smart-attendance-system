(function () {
  const slides = Array.from(document.querySelectorAll('.slide'));
  if (!slides.length) return;
  const dotsBox = document.getElementById('dots');
  const cap = document.getElementById('caption');
  const DURATION = 6500;
  let current = -1, timer = null;

  const dots = slides.map((_, i) => {
    const b = document.createElement('button');
    b.className = 'dot';
    b.setAttribute('aria-label', 'Show slide ' + (i + 1));
    b.style.setProperty('--dur', DURATION + 'ms');
    b.addEventListener('click', () => { go(i); });
    dotsBox.appendChild(b);
    return b;
  });

  function go(next) {
    if (next === current) return;
    const prev = slides[current];
    const incoming = slides[next];
    if (prev) {
      prev.classList.remove('active');
      prev.classList.add('prev');
      setTimeout(() => prev.classList.remove('prev'), 1800);
    }
    // reset any left-over state on the incoming slide, then reveal it
    incoming.classList.remove('prev');
    void incoming.offsetWidth;
    incoming.classList.add('active');
    dots.forEach((d, i) => {
      d.classList.remove('on');
      if (i === next) { void d.offsetWidth; d.classList.add('on'); }
    });
    cap.style.opacity = 0;
    setTimeout(() => {
      const s = slides[next].dataset;
      cap.innerHTML = '<strong></strong><span></span>';
      cap.firstChild.textContent = s.title;
      cap.lastChild.textContent = s.text;
      cap.style.opacity = 1;
    }, 350);
    current = next;
    clearTimeout(timer);
    timer = setTimeout(() => go((current + 1) % slides.length), DURATION);
  }

  slides[0].classList.add('first-load');
  go(0);
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) clearTimeout(timer);
    else timer = setTimeout(() => go((current + 1) % slides.length), DURATION);
  });
})();
