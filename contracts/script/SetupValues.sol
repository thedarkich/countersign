// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

/// @dev Exact decimal conversion and Gregorian end-of-day in China time.
library SetupValues {
    function baseUnits(string memory human, uint8 decimals) internal pure returns (uint256) {
        require(decimals <= 77, "unsupported precision");
        bytes memory value = bytes(human);
        require(value.length > 0, "empty amount");
        uint256 number;
        uint256 fractional;
        bool dot;
        bool digit;
        for (uint256 i; i < value.length; i++) {
            if (value[i] == ".") {
                require(!dot && digit && i + 1 < value.length, "invalid decimal");
                dot = true;
            } else {
                require(value[i] >= "0" && value[i] <= "9", "invalid amount");
                digit = true;
                number = number * 10 + uint8(value[i]) - 48;
                if (dot) fractional++;
            }
        }
        require(fractional <= decimals, "amount exceeds token precision");
        return number * 10 ** (uint256(decimals) - fractional);
    }

    function endOfChinaDay(string memory iso) internal pure returns (uint64) {
        bytes memory value = bytes(iso);
        require(value.length == 10 && value[4] == "-" && value[7] == "-", "invalid date");
        uint256 year = digits(value, 0, 4);
        uint256 month = digits(value, 5, 2);
        uint256 day = digits(value, 8, 2);
        require(year >= 1970 && year <= 9999 && month >= 1 && month <= 12, "invalid date");
        uint256[12] memory monthDays = [uint256(31), 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
        if (leap(year)) monthDays[1] = 29;
        require(day >= 1 && day <= monthDays[month - 1], "invalid date");
        uint256 daysSinceEpoch;
        for (uint256 y = 1970; y < year; y++) {
            daysSinceEpoch += leap(y) ? 366 : 365;
        }
        for (uint256 m = 1; m < month; m++) {
            daysSinceEpoch += monthDays[m - 1];
        }
        return uint64((daysSinceEpoch + day) * 1 days - 8 hours - 1);
    }

    function leap(uint256 year) private pure returns (bool) {
        return year % 4 == 0 && (year % 100 != 0 || year % 400 == 0);
    }

    function digits(bytes memory value, uint256 start, uint256 count) private pure returns (uint256 result) {
        for (uint256 i = start; i < start + count; i++) {
            require(value[i] >= "0" && value[i] <= "9", "invalid date");
            result = result * 10 + uint8(value[i]) - 48;
        }
    }
}
