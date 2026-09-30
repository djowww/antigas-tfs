/**
 * Tibia GIMUD Server - a free and open-source MMORPG server emulator
 * Copyright (C) 2017  Alejandro Mujica <alejandrodemujica@gmail.com>
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License along
 * with this program; if not, write to the Free Software Foundation, Inc.,
 * 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
 */

#include "otpch.h"

#include "player.h"
#include "talkaction.h"
#include "pugicast.h"

namespace {

bool parseAccountType(const std::string& value, AccountType_t& accountType)
{
	if (value == "normal") {
		accountType = ACCOUNT_TYPE_NORMAL;
	} else if (value == "tutor") {
		accountType = ACCOUNT_TYPE_TUTOR;
	} else if (value == "senior-tutor") {
		accountType = ACCOUNT_TYPE_SENIORTUTOR;
	} else if (value == "gamemaster") {
		accountType = ACCOUNT_TYPE_GAMEMASTER;
	} else if (value == "god") {
		accountType = ACCOUNT_TYPE_GOD;
	} else {
		return false;
	}
	return true;
}

} // namespace

TalkActions::TalkActions()
	: scriptInterface("TalkAction Interface")
{
	scriptInterface.initState();
}

TalkActions::~TalkActions()
{
	clear();
}

void TalkActions::clear()
{
	for (TalkAction* talkAction : talkActions) {
		delete talkAction;
	}
	talkActions.clear();

	scriptInterface.reInitState();
}

LuaScriptInterface& TalkActions::getScriptInterface()
{
	return scriptInterface;
}

std::string TalkActions::getScriptBaseName() const
{
	return "talkactions";
}

Event* TalkActions::getEvent(const std::string& nodeName)
{
	if (strcasecmp(nodeName.c_str(), "talkaction") != 0) {
		return nullptr;
	}
	return new TalkAction(&scriptInterface);
}

bool TalkActions::registerEvent(Event* event, const pugi::xml_node&)
{
	talkActions.push_front(static_cast<TalkAction*>(event)); // event is guaranteed to be a TalkAction
	return true;
}

TalkActionResult_t TalkActions::playerSaySpell(Player* player, SpeakClasses type, const std::string& words) const
{
	size_t wordsLength = words.length();
	for (TalkAction* talkAction : talkActions) {
		const std::string& talkactionWords = talkAction->getWords();
		size_t talkactionLength = talkactionWords.length();
		if (wordsLength < talkactionLength || strncasecmp(words.c_str(), talkactionWords.c_str(), talkactionLength) != 0) {
			continue;
		}

		std::string param;
		if (wordsLength != talkactionLength) {
			param = words.substr(talkactionLength);
			if (param.front() != ' ') {
				continue;
			}
			trim_left(param, ' ');

			char separator = talkAction->getSeparator();
			if (separator != ' ') {
				if (!param.empty()) {
					if (param.front() != separator) {
						continue;
					} else {
						param.erase(param.begin());
					}
				}
			}
		}

		const bool requiresAuthorization = !talkactionWords.empty() &&
			(talkactionWords.front() == '/' || talkactionWords.front() == '!');
		if (requiresAuthorization && !talkAction->isAuthorized(player)) {
			player->sendCancelMessage("You are not authorized to use this command.");
			return TALKACTION_BREAK;
		}

		if (talkAction->executeSay(player, param, type)) {
			return TALKACTION_CONTINUE;
		} else {
			return TALKACTION_BREAK;
		}
	}
	return TALKACTION_CONTINUE;
}

bool TalkAction::configureEvent(const pugi::xml_node& node)
{
	pugi::xml_attribute wordsAttribute = node.attribute("words");
	if (!wordsAttribute) {
		std::cout << "[Error - TalkAction::configureEvent] Missing words for talk action or spell" << std::endl;
		return false;
	}

	pugi::xml_attribute separatorAttribute = node.attribute("separator");
	if (separatorAttribute) {
		separator = pugi::cast<char>(separatorAttribute.value());
	}

	words = wordsAttribute.as_string();
	if (!words.empty() && (words.front() == '/' || words.front() == '!')) {
		pugi::xml_attribute permissionAttribute = node.attribute("permission");
		if (!permissionAttribute) {
			std::cout << "[Error - TalkAction::configureEvent] Missing permission policy for command " << words << std::endl;
			return false;
		}

		const std::string permission = permissionAttribute.as_string();
		TalkActionPolicy parsedAuthorization;
		if (permission == "public") {
			if (node.attribute("minaccounttype")) {
				std::cout << "[Error - TalkAction::configureEvent] Public command cannot set minaccounttype: " << words << std::endl;
				return false;
			}
		} else if (permission == "access") {
			parsedAuthorization.requireGroupAccess = true;
		} else if (permission == "broadcast") {
			if (node.attribute("minaccounttype")) {
				std::cout << "[Error - TalkAction::configureEvent] Broadcast command cannot set minaccounttype: " << words << std::endl;
				return false;
			}
			parsedAuthorization.requireBroadcastFlag = true;
		} else if (permission == "account") {
			parsedAuthorization.requireAccountType = true;
		} else {
			std::cout << "[Error - TalkAction::configureEvent] Unknown permission policy for " << words << ": " << permission << std::endl;
			return false;
		}

		pugi::xml_attribute minimumAccountTypeAttribute = node.attribute("minaccounttype");
		if (permission == "account" && !minimumAccountTypeAttribute) {
			std::cout << "[Error - TalkAction::configureEvent] Account policy requires minaccounttype for " << words << std::endl;
			return false;
		}
		if (minimumAccountTypeAttribute) {
			if (permission != "access" && permission != "account") {
				std::cout << "[Error - TalkAction::configureEvent] minaccounttype is not supported by policy for " << words << std::endl;
				return false;
			}
			if (!parseAccountType(minimumAccountTypeAttribute.as_string(), parsedAuthorization.minimumAccountType)) {
				std::cout << "[Error - TalkAction::configureEvent] Invalid minaccounttype for " << words << std::endl;
				return false;
			}
			parsedAuthorization.requireAccountType = true;
		}

		authorization = parsedAuthorization;
		authorizationConfigured = true;
	}
	return true;
}

bool TalkAction::isAuthorized(Player* player) const
{
	if (!authorizationConfigured || !player) {
		return false;
	}
	const bool hasGroupAccess = player->getGroup() && player->getGroup()->access;
	return authorization.allows(hasGroupAccess, player->getAccountType(), player->hasFlag(PlayerFlag_CanBroadcast));
}

std::string TalkAction::getScriptEventName() const
{
	return "onSay";
}

bool TalkAction::executeSay(Player* player, const std::string& param, SpeakClasses type) const
{
	//onSay(player, words, param, type)
	if (!scriptInterface->reserveScriptEnv()) {
		std::cout << "[Error - TalkAction::executeSay] Call stack overflow" << std::endl;
		return false;
	}

	ScriptEnvironment* env = scriptInterface->getScriptEnv();
	env->setScriptId(scriptId, scriptInterface);

	lua_State* L = scriptInterface->getLuaState();

	scriptInterface->pushFunction(scriptId);

	LuaScriptInterface::pushUserdata<Player>(L, player);
	LuaScriptInterface::setMetatable(L, -1, "Player");

	LuaScriptInterface::pushString(L, words);
	LuaScriptInterface::pushString(L, param);
	lua_pushnumber(L, type);

	return scriptInterface->callFunction(4);
}
