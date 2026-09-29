#ifndef FS_SCRIPT_ENVIRONMENT_INDEX_H
#define FS_SCRIPT_ENVIRONMENT_INDEX_H

#include <cstdint>

class ScriptEnvironmentIndex
{
	public:
		enum { CAPACITY = 16 };

		ScriptEnvironmentIndex() noexcept : index(-1) {}

		std::int32_t current() const noexcept {
			return index;
		}

		bool reserve() noexcept {
			if (index < -1 || index >= CAPACITY - 1) {
				return false;
			}

			++index;
			return true;
		}

		bool release() noexcept {
			if (index < 0 || index >= CAPACITY) {
				return false;
			}

			--index;
			return true;
		}

	private:
		std::int32_t index;
};

#endif
