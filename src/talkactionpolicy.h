/**
 * Tibia GIMUD Server - a free and open-source MMORPG server emulator
 * Copyright (C) 2017  Alejandro Mujica <alejandrodemujica@gmail.com>
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 */

#ifndef FS_TALKACTIONPOLICY_H_3904F6614D5245DFAF71530D16A8DF12
#define FS_TALKACTIONPOLICY_H_3904F6614D5245DFAF71530D16A8DF12

#include "enums.h"

struct TalkActionPolicy
{
	bool requireGroupAccess = false;
	bool requireBroadcastFlag = false;
	bool requireAccountType = false;
	AccountType_t minimumAccountType = ACCOUNT_TYPE_NORMAL;

	bool allows(bool hasGroupAccess, AccountType_t accountType, bool canBroadcast) const
	{
		return (!requireGroupAccess || hasGroupAccess) &&
		       (!requireBroadcastFlag || canBroadcast) &&
		       (!requireAccountType || accountType >= minimumAccountType);
	}
};

#endif
