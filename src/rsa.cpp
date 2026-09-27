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

#include "rsa.h"
#include <fstream>
#include <sstream>

bool RSA::loadKey(const char* filename)
{
	if (!filename || !*filename) return false;
	std::ifstream file(filename, std::ios::binary);
	if (!file) return false;
	char bytes[400];
	file.read(bytes, sizeof(bytes));
	if (!file.eof() || file.bad()) return false;
	std::istringstream input(std::string(bytes, static_cast<size_t>(file.gcount())));
	std::string pText, qText, extra;
	if (!(input >> pText >> qText) || (input >> extra)) return false;
	if (pText.empty() || qText.empty() || pText.size() > 160 || qText.size() > 160 ||
	    pText.find_first_not_of("0123456789") != std::string::npos ||
	    qText.find_first_not_of("0123456789") != std::string::npos) return false;

	mpz_t p, q, modulus, phi, p1, q1, exponent, gcd;
	mpz_inits(p, q, modulus, phi, p1, q1, exponent, gcd, nullptr);
	bool valid = mpz_set_str(p, pText.c_str(), 10) == 0 && mpz_set_str(q, qText.c_str(), 10) == 0;
	valid = valid && mpz_cmp(p, q) != 0 && mpz_probab_prime_p(p, 32) > 0 && mpz_probab_prime_p(q, 32) > 0;
	mpz_mul(modulus, p, q);
	// The legacy game protocol has a fixed 128-byte RSA block.
	valid = valid && mpz_sizeinbase(modulus, 2) == 1024;
	mpz_sub_ui(p1, p, 1);
	mpz_sub_ui(q1, q, 1);
	mpz_mul(phi, p1, q1);
	mpz_set_ui(exponent, 65537);
	mpz_gcd(gcd, exponent, phi);
	valid = valid && mpz_cmp_ui(gcd, 1) == 0;
	if (valid) setKey(pText.c_str(), qText.c_str());
	mpz_clears(p, q, modulus, phi, p1, q1, exponent, gcd, nullptr);
	return valid;
}

RSA::RSA()
{
	mpz_init(n);
	mpz_init2(d, 1024);
}

RSA::~RSA()
{
	mpz_clear(n);
	mpz_clear(d);
}

void RSA::setKey(const char* pString, const char* qString)
{
	mpz_t p, q, e;
	mpz_init2(p, 1024);
	mpz_init2(q, 1024);
	mpz_init(e);

	mpz_set_str(p, pString, 10);
	mpz_set_str(q, qString, 10);

	// e = 65537
	mpz_set_ui(e, 65537);

	// n = p * q
	mpz_mul(n, p, q);

	mpz_t p_1, q_1, pq_1;
	mpz_init2(p_1, 1024);
	mpz_init2(q_1, 1024);
	mpz_init2(pq_1, 1024);

	mpz_sub_ui(p_1, p, 1);
	mpz_sub_ui(q_1, q, 1);

	// pq_1 = (p -1)(q - 1)
	mpz_mul(pq_1, p_1, q_1);

	// d = e^-1 mod (p - 1)(q - 1)
	mpz_invert(d, e, pq_1);

	mpz_clear(p_1);
	mpz_clear(q_1);
	mpz_clear(pq_1);

	mpz_clear(p);
	mpz_clear(q);
	mpz_clear(e);
}

void RSA::decrypt(char* msg) const 
{
	mpz_t c, m;
	mpz_init2(c, 1024);
	mpz_init2(m, 1024);

	mpz_import(c, 128, 1, 1, 0, 0, msg);

	// m = c^d mod n
	mpz_powm(m, c, d, n);

	size_t count = (mpz_sizeinbase(m, 2) + 7) / 8;
	memset(msg, 0, 128 - count);
	mpz_export(msg + (128 - count), nullptr, 1, 1, 0, 0, m);

	mpz_clear(c);
	mpz_clear(m);
}
