// Receives pass alerts from the server (Web Push) and shows them, even when the app is closed.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", e => e.waitUntil(self.clients.claim()));

self.addEventListener("push", event => {
  let d = {};
  try {
    d = event.data ? event.data.json() : {};
  } catch {
    /* not JSON: fall back to the defaults below */
  }
  event.waitUntil(
    self.registration.showNotification(d.title || "Satellite pass", {
      body: d.body || "",
      tag: d.tag || "pass",
      data: { url: d.url || "/" },
    }),
  );
});

self.addEventListener("notificationclick", event => {
  event.notification.close();
  const target = new URL((event.notification.data && event.notification.data.url) || "/", self.registration.scope).href;
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(list => {
      for (const c of list) {
        if ("focus" in c) {
          if ("navigate" in c) c.navigate(target).catch(() => {});
          return c.focus();
        }
      }
      return self.clients.openWindow(target);
    }),
  );
});
