#include "../src/mapviewport.h"
#include <cassert>
#include <iostream>

int main() {
	MapViewport view;
	assert(view.width() == 18 && view.height() == 14);
	for (int x = 0; x <= 255; ++x) {
		for (int y = 0; y <= 255; ++y) {
			view.set(x, y);
			assert(view.x >= 8 && view.x <= 15 && view.y >= 6 && view.y <= 8);
			assert(view.width() >= 18 && view.width() <= 32);
			assert(view.height() >= 14 && view.height() <= 18);
			// Inclusive bounds contain exactly the serialized row/column count.
			assert((view.x + 1) - (-view.x) + 1 == view.width());
			assert((view.y + 1) - (-view.y) + 1 == view.height());
		}
	}
	view.set(20, 14); assert(view.width() == 22 && view.height() == 16); //19x13
	view.set(22, 16); assert(view.width() == 24 && view.height() == 18); //21x15
	view.set(16, 12); assert(view.width() == 18 && view.height() == 14); //classic
	std::cout << "PASS: 65,536 request pairs, classic, 19x13, 21x15, walk margins\n";
}
