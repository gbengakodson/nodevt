self.addEventListener('push', function(event) {
    let data = {};

    if (event.data) {
        data = event.data.json();
    }

    const options = {
        body: data.body || 'New update from NodeVT',
        icon: '/static/favicon.svg',
        badge: '/static/favicon.svg',
        vibrate: [200, 100, 200],
        data: {
            url: data.url || '/dashboard/',
            dateOfArrival: Date.now()
        },
        actions: [
            {
                action: 'open',
                title: 'Open App'
            },
            {
                action: 'close',
                title: 'Dismiss'
            }
        ]
    };

    event.waitUntil(
        self.registration.showNotification(data.title || 'NodeVT Update', options)
    );
});

self.addEventListener('notificationclick', function(event) {
    event.notification.close();

    if (event.action === 'open') {
        const urlToOpen = event.notification.data.url;
        event.waitUntil(
            clients.matchAll({type: 'window'}).then(windowClients => {
                for (let i = 0; i < windowClients.length; i++) {
                    const client = windowClients[i];
                    if (client.url === urlToOpen && 'focus' in client) {
                        return client.focus();
                    }
                }
                if (clients.openWindow) {
                    return clients.openWindow(urlToOpen);
                }
            })
        );
    }
});