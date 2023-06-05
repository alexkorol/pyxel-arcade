import pyxel
import random
import math

class Nutrient:
    def __init__(self, x, y, amount):
        self.x = x
        self.y = y
        self.amount = amount

class Environment:
    def __init__(self, temperature, humidity):
        self.temperature = temperature
        self.humidity = humidity

class FruitingBody:
    def __init__(self, x, y):
        self.x = x
        self.y = y

class Mycelium:
    def __init__(self, environment):
        self.hyphal_tips = [HyphalTip(64, 64, 1, 0)]
        self.branching_probability = 0.05
        self.neighbour_threshold = 8
        self.growth_speed = 0.3
        self.persistence_factor = 0.75
        self.environment = environment
        self.fruiting_body = None
        self.death_probability = 0.0001  # Probability of a hyphal tip dying in each update

    def grow(self):
        new_tips = []
        for tip in self.hyphal_tips:
            tip.grow(self.growth_speed)
            neighbours = self.find_neighbours(tip)
            if len(neighbours) < self.neighbour_threshold:
                if random.random() < self.branching_probability:
                    new_tips.append(tip.branch())
            tip.change_direction(self.persistence_factor)
            if random.random() < self.death_probability:
                self.hyphal_tips.remove(tip)
        self.hyphal_tips.extend(new_tips)

    def find_neighbours(self, tip):
        neighbours = []
        for other_tip in self.hyphal_tips:
            if other_tip != tip and other_tip.distance_to(tip) < self.neighbour_threshold:
                neighbours.append(other_tip)
        return neighbours

    def form_fruiting_body(self):
        # Check for necessary conditions and create a fruiting body if they are met
        if len(self.hyphal_tips) > 100 and self.environment.humidity > 80:
            self.fruiting_body = FruitingBody(self.hyphal_tips[0].x, self.hyphal_tips[0].y)

class HyphalTrail:
    def __init__(self, x, y):
        self.path = [(x, y)]

    def add_point(self, x, y):
        self.path.append((x, y))

class HyphalTip:
    def __init__(self, x, y, dx, dy):
        self.x = x
        self.y = y
        self.dx = dx
        self.dy = dy
        self.trail = HyphalTrail(x, y)

    def grow(self, speed):
        self.x += self.dx * speed
        self.y += self.dy * speed
        self.trail.add_point(self.x, self.y)

    def branch(self):
        angle = random.uniform(-3.14, 3.14)
        dx = self.dx + math.cos(angle)
        dy = self.dy + math.sin(angle)
        return HyphalTip(self.x, self.y, dx, dy)

    def change_direction(self, persistence_factor):
        angle = random.uniform(-3.14, 3.14)
        self.dx = (self.dx * persistence_factor + math.cos(angle) * (1 - persistence_factor))
        self.dy = (self.dy * persistence_factor + math.sin(angle) * (1 - persistence_factor))

    def distance_to(self, other_tip):
        return math.sqrt((self.x - other_tip.x)**2 + (self.y - other_tip.y)**2)

class App:
    def __init__(self):
        pyxel.init(128, 128)
        self.environment = Environment(20, 80)  # Initialize environment with arbitrary values
        self.mycelium = Mycelium(self.environment)
        self.nutrients = [Nutrient(random.randint(0, 127), random.randint(0, 127), 10) for _ in range(100)]
        pyxel.run(self.update, self.draw)

    def update(self):
        self.mycelium.grow()
        self.mycelium.form_fruiting_body()

    def draw(self):
        pyxel.cls(0)
        for tip in self.mycelium.hyphal_tips:
            for point in tip.trail.path:
                pyxel.pset(*point, 6)  # Draw the trail with color 6
            pyxel.pset(tip.x, tip.y, 7)  # Draw the tip with color 7
        for nutrient in self.nutrients:
            pyxel.pset(nutrient.x, nutrient.y, 4)
        if self.mycelium.fruiting_body is not None:
            pyxel.circ(self.mycelium.fruiting_body.x, self.mycelium.fruiting_body.y, 10, 7)

App()