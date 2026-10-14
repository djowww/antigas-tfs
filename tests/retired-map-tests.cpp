#include "otpch.h"
#include "game.h"
#include "configmanager.h"
#include "scheduler.h"
#include "databasetasks.h"
#include "rsa.h"
#include "iomap.h"
#include <boost/filesystem.hpp>
#include <fstream>
#include <stdexcept>

DatabaseTasks g_databaseTasks;
Dispatcher g_dispatcher;
Scheduler g_scheduler;
Game g_game;
ConfigManager g_config;
Monsters g_monsters;
Vocations g_vocations;
RSA g_RSA;

static void require(bool condition, const std::string& message)
{
    if (!condition) throw std::runtime_error(message);
}

template<typename T> static void number(std::string& bytes, T value)
{
    bytes.append(reinterpret_cast<const char*>(&value), sizeof(value));
}

static std::string node(uint8_t kind, const std::string& props, const std::string& children = "")
{
    std::string result(1, char(0xFE));
    result += char(kind);
    for (unsigned char byte : props) {
        if (byte >= 0xFD) result += char(0xFD);
        result += char(byte);
    }
    return result + children + char(0xFF);
}

static std::string item(uint16_t id, uint16_t actionId = 0, const std::string& children = "", const std::string& description = "")
{
    std::string props;
    number(props, id);
    if (actionId) {
        props += char(OTBM_ATTR_ACTION_ID);
        number(props, actionId);
    }
    if (!description.empty()) {
        props += char(OTBM_ATTR_DESC);
        number(props, uint16_t(description.size()));
        props += description;
    }
    return node(OTBM_ITEM, props, children);
}

static unsigned classicSwords = 0, shortSwords = 0, gold = 0, leaves = 0;
static void inspect(const Item* entry)
{
    require(Item::items[entry->getID()].group != ITEM_GROUP_DEPRECATED, "retired map node must not become a runtime item");
    if (const Container* container = entry->getContainer()) {
        require(container->size() <= container->capacity(), "recovery must fit classic container capacity");
        require(container->capacity() == Item::items[container->getID()].maxItems,
            "recovery must not inherit custom backpack capacity");
        for (ContainerIterator it = container->iterator(); it.hasNext(); it.advance()) {
            // iterator includes nested entries, inspect only direct children recursively below.
            if ((*it)->getParent() == container) inspect(*it);
        }
    } else {
        ++leaves;
        if (entry->getID() == 3264) {
            ++classicSwords;
            require(entry->getActionId() >= 1000 && entry->getActionId() <= 1025,
                "classic descendant attributes must survive recovery");
        } else if (entry->getID() == 3294) {
            ++shortSwords;
            require(entry->getActionId() == 777, "nested classic descendant attributes must survive recovery");
        } else if (entry->getID() == 3031) {
            ++gold;
            require(entry->getItemCount() == 17, "classic stack counts must survive recovery");
        }
    }
}

int main()
{
    boost::filesystem::path scratch;
    try {
        require(Item::items.loadItems(), "native item definitions must load");
        std::string manyChildren;
        for (uint16_t i = 0; i < 26; ++i) manyChildren += item(3264, 1000 + i);
        std::string goldProps;
        number(goldProps, uint16_t(3031));
        goldProps += char(OTBM_ATTR_COUNT);
        goldProps += char(17);
        manyChildren += item(5110, 0, node(OTBM_ITEM, goldProps) + item(3159), "retired nested name");
        const std::string recovered = item(3253, 555, manyChildren, "retired carrier attributes must disappear");
        const std::string classic = item(2854, 888,
            item(3157) + item(3253, 0, item(3294, 777)), "original classic description");
        std::string tileProps(2, char(0));
        tileProps += char(OTBM_ATTR_ITEM);
        number(tileProps, uint16_t(102));
        tileProps += char(OTBM_ATTR_ITEM);
        number(tileProps, uint16_t(3157));
        std::string area;
        number(area, uint16_t(100));
        number(area, uint16_t(100));
        area += char(7);
        std::string header;
        number(header, uint32_t(2));
        number(header, uint16_t(256));
        number(header, uint16_t(256));
        number(header, uint32_t(3));
        number(header, uint32_t(0));
        const std::string fixture = "OTBM" + node(OTBM_ROOTV1, header,
            node(OTBM_MAP_DATA, "", node(OTBM_TILE_AREA, area,
                node(OTBM_TILE, tileProps, item(3159) + item(435) + recovered + classic))));
        scratch = boost::filesystem::temp_directory_path() / boost::filesystem::unique_path("retired-map-%%%%-%%%%.otbm");
        {
            std::ofstream file(scratch.string(), std::ios::binary);
            file.write(fixture.data(), fixture.size());
        }
        Map map;
        IOMap reader;
        const bool loaded = reader.loadMap(&map, scratch.string());
        require(loaded, "map with retired portable nodes must load: " + reader.getLastErrorString());
        Tile* tile = map.getTile(100, 100, 7);
        require(tile && tile->getGround() && tile->getGround()->getID() == 102,
            "original ground must retain its ID");
        bool sawStructure = false, sawClassic = false, sawRecovered = false;
        require(tile->getItemList() != nullptr, "fixture item list must exist");
        for (Item* entry : *tile->getItemList()) {
            sawStructure |= entry->getID() == 435;
            if (entry->getID() == 2854 && entry->getActionId() == 888) {
                sawClassic = true;
                require(entry->getSpecialDescription() == "original classic description", "original container attributes must remain unchanged");
            } else if (entry->getID() == 2854) {
                sawRecovered = true;
                require(entry->getActionId() == 0 && entry->getSpecialDescription().empty(),
                    "retired carrier attributes must not transfer to recovery wrapper");
                require(entry->getContainer()->getItemByIndex(0)->getActionId() == 1000 &&
                    entry->getContainer()->getItemByIndex(19)->getContainer() != nullptr,
                    "recovery must retain serialized order with nineteen direct items then overflow");
            }
            inspect(entry);
        }
        require(sawStructure && sawClassic && sawRecovered, "classic structure/container and recovered carrier must all survive");
        require(classicSwords == 26 && shortSwords == 1 && gold == 1 && leaves == 29,
            "all ordinary descendants must survive and retired leaves must disappear");
        boost::filesystem::remove(scratch);
        std::cout << "PASS: read-only map retirement preserves ground, structure, classic descendants and overflow\n";
        return 0;
    } catch (const std::exception& error) {
        if (!scratch.empty()) boost::filesystem::remove(scratch);
        std::cerr << "FAIL: " << error.what() << '\n';
        return 1;
    }
}
