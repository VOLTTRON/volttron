#include <iostream>
#include "python_cbc_building.cpp"

int main()
{
	char c;
	init_building();
	std::cin >> c;
	free_building();
	return 0;
}
