#ifndef FS_HUNT_SUPPLY_H
#define FS_HUNT_SUPPLY_H

#include "item.h"
#include "player.h"
#include "networkmessage.h"

// Dispatcher-local observation of a concrete use. Retain the item across scripts,
// transforms and removal; never infer consumption from inventory movements.
class HuntSupplyUse final {
public:
    HuntSupplyUse(Player* actor, Item* used, bool fluidUse = false, bool expires = false)
        : player(actor), item(used), allowFluid(fluidUse), expiration(expires) {
        if (!player || !item || !item->isPickupable() || item->getContainer()) { item = nullptr; return; }
        id = item->getID();
        // Currency conversion/payment is not hunting supply consumption.
        if (id == 3031 || id == 3035 || id == 3043 || id == 5130) { item = nullptr; return; }
        item->incrementReferenceCounter();
        name = item->getName();
        stackable = item->isStackable();
        count = item->getItemCount();
        charges = item->getCharges();
        fluid = Item::items[id].isFluidContainer() ? item->getFluidType() : 0;
    }

    ~HuntSupplyUse() {
        if (!item) return;
        const bool replaced = item->isRemoved() || item->getID() != id;
        uint32_t spent = 0;
        if (fluid != 0) {
            if (allowFluid && (replaced || item->getFluidType() == 0)) spent = 1;
        } else if (charges > 0) {
            const uint32_t remaining = replaced ? 0 : item->getCharges();
            if (remaining < charges) spent = charges - remaining;
        } else if (stackable) {
            const uint32_t remaining = replaced ? 0 : item->getItemCount();
            if (remaining < count) spent = count - remaining;
        } else if (item->isRemoved() || (expiration && replaced)) {
            spent = 1;
        }
        if (spent > 0) {
            // Match the existing bounded raw array decoder (including older clients).
            for (char& c : name) {
                if (c == '"' || c == '\\' || static_cast<unsigned char>(c) < 32) c = ' ';
            }
            name.resize(std::min<size_t>(80, name.size()));
            NetworkMessage message;
            message.addByte(0x32);
            message.addByte(123);
            message.addString("{\"" + name + "\"," + std::to_string(spent) + "," + std::to_string(id) + "}");
            player->sendNetworkMessage(message);
        }
        item->decrementReferenceCounter();
    }

    HuntSupplyUse(const HuntSupplyUse&) = delete;
    HuntSupplyUse& operator=(const HuntSupplyUse&) = delete;

private:
    Player* player;
    Item* item;
    bool allowFluid, expiration, stackable = false;
    uint16_t id = 0, count = 0, charges = 0, fluid = 0;
    std::string name;
};
#endif
