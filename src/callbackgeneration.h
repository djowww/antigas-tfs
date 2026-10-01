#ifndef FS_CALLBACK_GENERATION_H_74B1C80F6E4A4D00B3706090936E1F6D
#define FS_CALLBACK_GENERATION_H_74B1C80F6E4A4D00B3706090936E1F6D

#include <atomic>
#include <cstdint>
#include <functional>
#include <memory>

// Invalidates queued callbacks without requiring the scheduler to still own
// their event IDs. A guarded callback keeps only a weak reference to this
// state, so it becomes a no-op after its owner is destroyed or invalidated.
// This is a queued-delivery guard, not a barrier for a callback already past
// the check. Owner teardown/invalidation must be serialized with callback
// execution; current users route both through the game dispatcher.
class CallbackGeneration
{
	struct State {
		State() : value(1) {}
		std::atomic<uint64_t> value;
	};

	public:
		using Snapshot = uint64_t;

		CallbackGeneration() : state(std::make_shared<State>()) {}

		Snapshot snapshot() const noexcept
		{
			return state->value.load(std::memory_order_acquire);
		}

		void invalidate() noexcept
		{
			state->value.fetch_add(1, std::memory_order_acq_rel);
		}

		template <typename Callback>
		std::function<void()> guard(Snapshot expected, Callback callback) const
		{
			std::weak_ptr<State> weakState = state;
			return [weakState, expected, callback]() mutable {
				const std::shared_ptr<State> currentState = weakState.lock();
				if (!currentState || currentState->value.load(std::memory_order_acquire) != expected) {
					return;
				}
				callback();
			};
		}

	private:
		std::shared_ptr<State> state;
};

#endif
