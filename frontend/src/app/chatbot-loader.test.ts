import { expect, test } from 'vitest';
import pageTemplate from '../../index.html?raw';

test('loads the configured chatbot widget from the document head', () => {
  expect(pageTemplate).toContain(
    'src="https://coastworks-sitechat.vercel.app/widget/chatbot.js"',
  );
  expect(pageTemplate).toContain('data-site-id="dc0db006c4de"');
  expect(pageTemplate).toContain(
    'data-api-url="https://coastworks-sitechat.vercel.app"',
  );
});
