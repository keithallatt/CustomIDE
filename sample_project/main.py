"""
Sample main, sample change
"""

#todo(keith): write more code!

class Car:
    def __init__(self):
        self.speed = 0
        self.odometer = 0

    def accelerate(self):
        self.speed += 1

    def brake(self):
        if self.speed > 0:
            self.speed -= 1

    def time_step(self):
        self.odometer += self.speed

    def __str__(self):
        return f"Car going {self.speed}kph has travelled {self.odometer}km."


if __name__ == "__main__":
    my_car = Car()

    for i in range(10):
        my_car.accelerate()
        my_car.time_step()

    for i in range(5):
        my_car.brake()
        my_car.time_step()

    print(my_car)
