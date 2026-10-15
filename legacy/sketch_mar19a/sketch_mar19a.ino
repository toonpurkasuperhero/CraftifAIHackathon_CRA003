#define TRIG_PIN 5
#define ECHO_PIN 18
#define PIR_PIN 21
#define BUZZER_PIN 2

float threshold = 20.0; // distance in cm

void setup() {
  Serial.begin(115200);

  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  pinMode(PIR_PIN, INPUT);
  pinMode(BUZZER_PIN, OUTPUT);
}

void loop() {
  // ---- Ultrasonic ----
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);

  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  long duration = pulseIn(ECHO_PIN, HIGH);
  float distance = duration * 0.034 / 2;

  // ---- PIR ----
  int motion = digitalRead(PIR_PIN);

  // ---- Serial Output ----
  Serial.print("Distance: ");
  Serial.print(distance);
  Serial.print(" cm | PIR: ");
  Serial.println(motion ? "Motion Detected" : "No Motion");

  // ---- Logic ----
  if ((distance > 0 && distance < threshold) || motion == HIGH) {
    digitalWrite(BUZZER_PIN, HIGH); // ON
  } else {
    digitalWrite(BUZZER_PIN, LOW);  // OFF
  }

  delay();
}