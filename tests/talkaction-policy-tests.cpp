#include "otpch.h"
#include "talkactionpolicy.h"

#include <stdexcept>

static void require(bool condition, const char* message)
{
	if (!condition) throw std::runtime_error(message);
}

int main()
{
	TalkActionPolicy publicCommand;
	require(publicCommand.allows(false, ACCOUNT_TYPE_NORMAL, false), "public policy must allow normal players");

	TalkActionPolicy staffCommand;
	staffCommand.requireGroupAccess = true;
	require(!staffCommand.allows(false, ACCOUNT_TYPE_GOD, true), "account type alone must not satisfy group access");
	require(staffCommand.allows(true, ACCOUNT_TYPE_GAMEMASTER, false), "group access must preserve staff-only commands");

	TalkActionPolicy tutorCommand;
	tutorCommand.requireAccountType = true;
	tutorCommand.minimumAccountType = ACCOUNT_TYPE_TUTOR;
	require(!tutorCommand.allows(false, ACCOUNT_TYPE_NORMAL, false), "normal account must not satisfy tutor command policy");
	require(tutorCommand.allows(false, ACCOUNT_TYPE_TUTOR, false), "tutor account must satisfy tutor command policy");

	TalkActionPolicy seniorTutorCommand;
	seniorTutorCommand.requireAccountType = true;
	seniorTutorCommand.minimumAccountType = ACCOUNT_TYPE_SENIORTUTOR;
	require(!seniorTutorCommand.allows(true, ACCOUNT_TYPE_TUTOR, true), "tutor must not satisfy senior tutor policy");
	require(seniorTutorCommand.allows(false, ACCOUNT_TYPE_SENIORTUTOR, false), "senior tutor must satisfy account policy without a group access flag");

	TalkActionPolicy godStaffCommand;
	godStaffCommand.requireGroupAccess = true;
	godStaffCommand.requireAccountType = true;
	godStaffCommand.minimumAccountType = ACCOUNT_TYPE_GOD;
	require(!godStaffCommand.allows(true, ACCOUNT_TYPE_GAMEMASTER, true), "group access alone must not satisfy God-only policy");
	require(!godStaffCommand.allows(false, ACCOUNT_TYPE_GOD, true), "God account alone must not satisfy group access policy");
	require(godStaffCommand.allows(true, ACCOUNT_TYPE_GOD, false), "God with group access must satisfy combined policy");

	TalkActionPolicy broadcastCommand;
	broadcastCommand.requireBroadcastFlag = true;
	require(!broadcastCommand.allows(true, ACCOUNT_TYPE_GOD, false), "staff access must not replace the broadcast flag");
	require(broadcastCommand.allows(false, ACCOUNT_TYPE_NORMAL, true), "broadcast flag policy must preserve flag-based authorization");
	return 0;
}
