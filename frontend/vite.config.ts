import { defineConfig } from 'vite';
import tailwindcss from '@tailwindcss/vite';
import { fileURLToPath, URL } from 'node:url';
export default defineConfig({ plugins: [tailwindcss()], resolve: { alias: { '@': fileURLToPath(new URL('.', import.meta.url)) } }, base: './', build: { rollupOptions: { input: { home: fileURLToPath(new URL('./home.html', import.meta.url)), calendar: fileURLToPath(new URL('./calendar.html', import.meta.url)), tax: fileURLToPath(new URL('./tax.html', import.meta.url)), assistant: fileURLToPath(new URL('./assistant.html', import.meta.url)), live: fileURLToPath(new URL('./live.html', import.meta.url)) } } } });
