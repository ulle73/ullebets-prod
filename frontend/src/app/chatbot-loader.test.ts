import { expect, test } from 'vitest';
import pageTemplate from '../../index.html?raw';

test('loads the configured chatbot widget from the document head', () => {
  expect(pageTemplate).toContain(
    "s.src = 'http://127.0.0.1:8000/widget/chatbot.js';",
  );
  expect(pageTemplate).toContain('s.async = true;');
  expect(pageTemplate).toContain("s.dataset.siteId = 'dc0db006c4de';");
  expect(pageTemplate).toContain(
    "s.dataset.apiUrl = 'http://127.0.0.1:8000';",
  );
  expect(pageTemplate).toContain('document.head.appendChild(s);');
});
