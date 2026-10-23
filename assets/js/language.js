(function () {
  'use strict';
  var language = 'en';
  try {
    var requested = new URLSearchParams(window.location.search).get('lang');
    var saved = localStorage.getItem('homepage-language');
    language = requested === 'zh' || requested === 'en' ? requested : saved === 'zh' ? 'zh' : 'en';
  } catch (error) { /* English remains available when storage is disabled. */ }
  document.documentElement.dataset.language = language;
  document.documentElement.lang = language === 'zh' ? 'zh-CN' : 'en';
  function applyLanguage(next) {
    language = next;
    document.documentElement.dataset.language = next;
    document.documentElement.lang = next === 'zh' ? 'zh-CN' : 'en';
    document.querySelectorAll('[data-en][data-zh]').forEach(function (element) {
      element.textContent = element.getAttribute('data-' + next);
    });
    document.querySelectorAll('[data-alt-en][data-alt-zh]').forEach(function (image) {
      image.alt = image.getAttribute('data-alt-' + next);
    });
    document.querySelectorAll('[data-language]').forEach(function (button) {
      if (button.tagName === 'BUTTON') button.setAttribute('aria-pressed', String(button.dataset.language === next));
    });
    document.querySelectorAll('[data-language-content]').forEach(function (block) {
      block.hidden = block.dataset.languageContent !== next;
    });
    try { localStorage.setItem('homepage-language', next); } catch (error) {}
    // Keep shared language URLs consistent when switching locally.
    var url = new URL(window.location.href);
    if (url.searchParams.has('lang')) {
      url.searchParams.set('lang', next);
      window.history.replaceState(null, '', url);
    }
    window.dispatchEvent(new Event('resize'));
  }
  document.addEventListener('DOMContentLoaded', function () {
    var titles = { 'About me': '关于我', 'Research': '科学研究', 'Publications': '学术论文', 'Blog posts': '博客', 'Blog Posts': '博客' };
    document.querySelectorAll('.page__title').forEach(function (title) {
      var english = title.textContent.trim();
      if (titles[english]) {
        title.dataset.en = english;
        title.dataset.zh = titles[english];
      }
    });
    document.querySelectorAll('.language-switch button').forEach(function (button) {
      button.addEventListener('click', function () { applyLanguage(button.dataset.language); });
    });
    applyLanguage(language);
  });
}());
