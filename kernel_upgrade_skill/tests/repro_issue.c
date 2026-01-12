#include <linux/netdevice.h>

void my_driver_init(struct net_device *dev) {
    // OLD API: netif_napi_add(dev, &ep->napi, my_poll, 64);
    // NEW API expected: netif_napi_add_weight(dev, &ep->napi, my_poll, 64);
    netif_napi_add(dev, &ep->napi, my_poll, 64);
}
