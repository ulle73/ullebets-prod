import { expect, test } from 'vitest';
import pageTemplate from '../../index.html?raw';

test('loads the configured chatbot widget from the document head', () => {
  expect(pageTemplate).toContain(
    'src="https://coastworks-sitechat.vercel.app/widget/chatbot.js"',
  );
  expect(pageTemplate).toContain('data-site-id="56e53c18828b"');
  expect(pageTemplate).toContain(
    'data-api-url="https://coastworks-sitechat.vercel.app"',
  );
});
