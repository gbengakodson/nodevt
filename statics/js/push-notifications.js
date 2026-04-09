// Register Service Worker
if ('serviceWorker' in navigator && 'PushManager' in window) {
    navigator.serviceWorker.register('/static/js/sw.js')
        .then(function(swReg) {
            console.log('Service Worker registered', swReg);
            window.swRegistration = swReg;

            // Check for existing subscription
            swReg.pushManager.getSubscription().then(function(subscription) {
                if (subscription) {
                    console.log('Already subscribed', subscription.endpoint);
                } else {
                    // Auto-subscribe after registration
                    subscribeUser();
                }
            });
        })
        .catch(function(error) {
            console.error('Service Worker Error', error);
        });
}

// Subscribe user for push notifications
function subscribeUser() {
    if (!window.swRegistration) return;

    const applicationServerKey = urlB64ToUint8Array('YOUR_VAPID_PUBLIC_KEY');

    window.swRegistration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: applicationServerKey
    })
    .then(function(subscription) {
        console.log('User is subscribed:', subscription);

        // Send subscription to backend
        fetch('/api/notifications/subscribe/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            },
            body: JSON.stringify(subscription)
        });
    })
    .catch(function(err) {
        console.error('Failed to subscribe user: ', err);
    });
}

function urlB64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - base64String.length % 4) % 4);
    const base64 = (base64String + padding)
        .replace(/\-/g, '+')
        .replace(/_/g, '/');
    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);
    for (let i = 0; i < rawData.length; ++i) {
        outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
}