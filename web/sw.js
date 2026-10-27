// Minimal service worker so Android offers "install app". The game needs the
// server anyway, so requests simply go to the network.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));
self.addEventListener("fetch", () => {});
