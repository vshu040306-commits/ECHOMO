#include <Adafruit_NeoPixel.h>
#include "DFRobot_Gesture_Touch.h"
#include <SoftwareSerial.h>

#define PIN6 6               // NeoPixel 数据引脚
#define LED_COUNT 60        // 灯珠数量
const int PIN_PLAYBACK = 7;   // 播放按钮
const int PIN_SWITCH = 4;     // 切换开关
const int PIN_RECORDING = 2;  // 录音结束按钮

Adafruit_NeoPixel strip = Adafruit_NeoPixel(LED_COUNT, PIN6, NEO_GRB + NEO_KHZ800);
SoftwareSerial mySerial(10, 11);  // RX, TX
DFRobot_Gesture_Touch DFGT(&mySerial);

// 手势控制状态
bool gestureEnabled = false;

// 去抖动相关变量
bool buttonDown = false;        // 按钮按下标志
bool lastButtonState = HIGH;
unsigned long lastDebounceTime = 0;
const unsigned long DEBOUNCE_DELAY = 30; 

unsigned long lastPlayTime = 0;
unsigned long lastSwitchTime = 0;
unsigned long lastRecordTime = 0;

int lastPlayState = HIGH;
int lastSwitchState = HIGH;
int lastRecordState = HIGH;

void setup() {
  Serial.begin(9600);
  strip.begin();
  strip.show();             // 清除灯光
  mySerial.begin(9600);     // 手势传感器串口

  DFGT.setGestureDistance(15);         // 设置感应距离
  DFGT.enableFunction(DFGT_FUN_ALL);   // 启用全部手势识别

   // 初始化引脚为带上拉电阻的输入模式
  pinMode(PIN_PLAYBACK, INPUT_PULLUP);
  pinMode(PIN_SWITCH, INPUT_PULLUP);
  pinMode(PIN_RECORDING, INPUT_PULLUP);
  
  // 初始化串口通信（波特率需与Python代码一致）
  Serial.println("Arduino initialized");
  setColor(0);                         // 初始关闭灯光
  Serial.println("系统初始化完成，按下按钮启用手势识别。");
} 

void loop() {
  playbutton();
  switchbutton();
  endbutton();

  gesturebutton();
    if (gestureEnabled) {
      int8_t rslt = DFGT.getAnEvent();
      if (rslt != DF_ERR) {
        switch (rslt) {
          case DFGT_EVT_BACK:
            Serial.println("手势：上滑（彩虹）");
            rainbow(10);
            break;
          case DFGT_EVT_FORWARD:
            Serial.println("手势：下滑（蓝色）");
            setColor(strip.Color(0, 0, 255));
            break;
          case DFGT_EVT_RIGHT:
            Serial.println("手势：右滑（柠檬黄）");
            setColor(strip.Color(255, 255, 0));
            break;
          case DFGT_EVT_LEFT:
            Serial.println("手势：左滑（白灯闪烁）");
            blinkEffect(300);
            break;
          default:
            break;
      }
    }
  }
}

// 按钮检测与手势识别切换
void gesturebutton() {
  int reading = digitalRead(PIN_PLAYBACK);
  if (reading != lastPlayState) {
    lastDebounceTime = millis();
  }

  if ((millis() - lastDebounceTime) > DEBOUNCE_DELAY) {
    static bool buttonState = LOW;
    if (reading != buttonState) {
      buttonState = reading;
      if (buttonState == HIGH) { 
        gestureEnabled = !gestureEnabled;

        Serial.println(gestureEnabled ? "✅ Gesture recognition: On " : "❌ Gesture recognition: off");

        if (!gestureEnabled) {
          setColor(0);  
        }
      }
    }
  }
  lastButtonState = reading;
}

void playbutton() {
  int reading = digitalRead(PIN_PLAYBACK);

  if (reading != lastPlayState) {
    lastPlayTime = millis();
  }

  if ((millis() - lastPlayTime) > DEBOUNCE_DELAY) {
    static bool buttonState = LOW;
    if (reading != buttonState) {
      buttonState = reading;
      if (buttonState == HIGH) { 
        Serial.println("PLAYBACK"); 
      }
    }
  }
  lastPlayState = reading;
}

void endbutton() {
  int reading = digitalRead(PIN_RECORDING);

  if (reading != lastRecordState) {
    lastRecordTime = millis();
  }

  if ((millis() - lastRecordTime) > DEBOUNCE_DELAY) {
    static bool buttonState = LOW;
    if (reading != buttonState) {
      buttonState = reading;
      if (buttonState == HIGH) { 
        Serial.println("ENDRECORDING");
      }
    }
  }

  lastRecordState = reading;
}

void switchbutton() {
  int reading = digitalRead(PIN_SWITCH);

  if (reading != lastSwitchState) {
    lastSwitchTime = millis();
  }

  if ((millis() - lastSwitchTime) > DEBOUNCE_DELAY) {
    static bool buttonState = LOW;
    if (reading != buttonState) {
      buttonState = reading;
      if (buttonState == HIGH) { 
        Serial.println("SWITCH"); 
      }
    }
  }
  lastSwitchState = reading;
}
// 设置全灯颜色
void setColor(uint32_t color) {
  for (int i = 0; i < strip.numPixels(); i++) {
    strip.setPixelColor(i, color);
  }
  strip.show();
}

// 彩虹流动效果（支持中断）
void rainbow(uint8_t wait) {
  for (int j = 0; j < 256 && gestureEnabled; j++) {
    for (int i = 0; i < strip.numPixels(); i++) {
      if (!gestureEnabled) {
        setColor(0);  // 手势关闭时立即清除
        return;
      }
      strip.setPixelColor(i, Wheel((i + j) & 255));
    }
    strip.show();
    delay(wait);
  }
}

// 白灯闪烁两次（支持中断）
void blinkEffect(uint8_t delayTime) {
  for (int i = 0; i < 2; i++) {
    if (!gestureEnabled) {
      setColor(0);
      return;
    }
    setColor(strip.Color(255, 255, 255));  // 白灯亮
    delay(delayTime);

    if (!gestureEnabled) {
      setColor(0);
      return;
    }
    setColor(0);  // 灯灭
    delay(delayTime);
  }
}

// 彩虹色轮函数
uint32_t Wheel(byte WheelPos) {
  if (WheelPos < 85) {
    return strip.Color(WheelPos * 3, 255 - WheelPos * 3, 0);
  } 
  else if (WheelPos < 170) {
    WheelPos -= 85;
    return strip.Color(255 - WheelPos * 3, 0, WheelPos * 3);
  } 
  else {
    WheelPos -= 170;
    return strip.Color(0, WheelPos * 3, 255 - WheelPos * 3);
  }
}

