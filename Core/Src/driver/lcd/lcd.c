/*
 * lcd.c
 *
 *  Created on: 2026. 10. 21.
 *      Author: kccistc
 */

#include "lcd.h"

#define LCD_RS	0
#define LCD_RW	1
#define LCD_E	2
#define LCD_BL	3

extern I2C_HandleTypeDef hi2c1;

uint8_t lcdData = 0;

void Lcd_sendData(uint8_t data)
{
	HAL_I2C_Master_Transmit(&hi2c1, 0x27<<1, &data, 1, 100);
}

void Lcd_cmdMode(void)
{
	lcdData &= ~(1 << LCD_RS); // 0
}

void Lcd_dataMode(void)
{
	lcdData |= (1 << LCD_RS); // 1
}

void Lcd_writeMode(void)
{
	lcdData &= ~(1 << LCD_RW);
}

void Lcd_enHigh(void)
{
	lcdData |= (1 << LCD_E);
	Lcd_sendData(lcdData);
}

void Lcd_enLow(void)
{
	lcdData &= ~(1 << LCD_E);
	Lcd_sendData(lcdData);
}

void Lcd_backlightOn(void)
{
	lcdData |= (1 << LCD_BL);
	Lcd_sendData(lcdData);
}

void Lcd_backlightOff(void)
{
	lcdData &= ~(1 << LCD_BL);
	Lcd_sendData(lcdData);
}

void Lcd_writeNibble(uint8_t data)
{
	Lcd_enHigh();
	lcdData = (lcdData & 0x0f) | (data & 0xf0);
	Lcd_sendData(lcdData); // send data into i2c interface
	Lcd_enLow();
}

void Lcd_writeByte(uint8_t data)
{
	Lcd_writeNibble(data); // data High 4bit
	data <<= 4;
	Lcd_writeNibble(data); // data Low 4bit
}

void Lcd_writeCmdData(uint8_t data)
{
	Lcd_cmdMode();
	Lcd_writeMode();
	Lcd_writeByte(data);

}

void Lcd_writeCharData(uint8_t data)
{
	Lcd_dataMode();
	Lcd_writeMode();
	Lcd_writeByte(data);

}


void Lcd_init(void)
{
	HAL_Delay(40);
	Lcd_cmdMode();
	Lcd_writeMode();
	Lcd_writeNibble(0x30);
	HAL_Delay(5);
	Lcd_writeNibble(0x30);
	HAL_Delay(1);
	Lcd_writeNibble(0x30);

	Lcd_writeNibble(0x20);
	Lcd_writeByte(0x28); // Function set 4bit
	Lcd_writeByte(0x08); // display off
	Lcd_writeByte(0x01); // display clear
	Lcd_writeByte(0x06); // entry mode set
	Lcd_writeByte(0x0C); // display on
	Lcd_backlightOn();
}

void Lcd_writeString(char *str)
{
	for (int i=0; str[i]; i++)
	{
		Lcd_writeCharData(str[i]);
	}
}

void Lcd_gotoXY(uint8_t row, uint8_t col)
{
	col %= 16;
	row %= 2;

	uint8_t lcdRegAddr = (0x40 * row) + col;
	uint8_t cmd = 0x80 + lcdRegAddr;
	Lcd_writeCmdData(cmd);
}

void Lcd_writeStringXY(uint8_t row, uint8_t col, char *str)
{
	Lcd_gotoXY(row, col);
	Lcd_writeString(str);
}
