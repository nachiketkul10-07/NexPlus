import '@testing-library/jest-dom';

// JSDOM has no native IntersectionObserver; Framer Motion's viewport reveal
// feature must still mount in component tests without pretending elements intersect.
if (!('IntersectionObserver' in globalThis)) {
  class TestIntersectionObserver implements IntersectionObserver {
    readonly root = null;
    readonly rootMargin = '0px';
    readonly thresholds = [0];
    observe() {}
    unobserve() {}
    disconnect() {}
    takeRecords(): IntersectionObserverEntry[] { return []; }
  }
  globalThis.IntersectionObserver = TestIntersectionObserver;
}
