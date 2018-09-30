from PythonClientAPI.game.PointUtils import *
from PythonClientAPI.game.Entities import FriendlyUnit, EnemyUnit, Tile
from PythonClientAPI.game.Enums import Team
from PythonClientAPI.game.World import World
from PythonClientAPI.game.TileUtils import TileUtils
import operator
import numpy as np
import copy


class PlayerAI:

    def __init__(self):
        ''' Initialize! '''
        self.turn_count = 0             # game turn count
        self.target = None              # target to send unit to!
        self.outbound = True            # is the unit leaving, or returning?

        self.world = None
        self.friendly_unit = None
        self.enemy_units = None

        self.anchor = None

        self.targets = []
        self.return_flag = False
        self.return_midpoint = None


    def do_move(self, world, friendly_unit, enemy_units):
        '''
        This method is called every turn by the game engine.
        Make sure you call friendly_unit.move(target) somewhere here!

        Below, you'll find a very rudimentary strategy to get you started.
        Feel free to use, or delete any part of the provided code - Good luck!

        :param world: world object (more information on the documentation)
            - world: contains information about the game map.
            - world.path: contains various pathfinding helper methods.
            - world.util: cosntains various tile-finding helper methods.
            - world.fill: contains various flood-filling helper methods.

        :param friendly_unit: FriendlyUnit object
        :param enemy_units: list of EnemyUnit objects
        '''
        self.world = world
        self.friendly_unit = friendly_unit
        self.enemy_units = enemy_units

        # increment turn count
        self.turn_count += 1

        # if unit is dead, stop making moves.
        if friendly_unit.status == 'DISABLED':
            print("Turn {0}: Disabled - skipping move.".format(str(self.turn_count)))
            self.target = None
            self.outbound = True
            return
        position = self.friendly_unit.position

        if self.anchor is None:
            nearest_neutral = self.world.util.get_closest_neutral_territory_from(position, set())
            next_move = self.world.path.get_next_point_in_shortest_path(position, nearest_neutral.position)

        elif position in self.targets or self.return_flag:
            closest_friendly_territory = self.world.util.get_closest_friendly_territory_from(position, self.friendly_unit.snake).position

            # calculate which route to take
            if self.return_midpoint is None:
                point_a = (position[0], closest_friendly_territory[1])
                point_b = (closest_friendly_territory[0], position[1])

                # point A
                path_a = copy.deepcopy(self.friendly_unit.snake)

                to_point_a = self.world.path.get_shortest_path(position, point_a, self.friendly_unit.snake)
                if to_point_a is not None:
                    path_a = path_a.union(set(to_point_a))
                to_friend_a = self.world.path.get_shortest_path(point_a, closest_friendly_territory, self.friendly_unit.snake)
                if to_friend_a is not None:
                    path_a = path_a.union(set(to_friend_a))

                # point B
                path_b = copy.deepcopy(self.friendly_unit.snake)

                to_point_b = self.world.path.get_shortest_path(position, point_b, self.friendly_unit.snake)
                if to_point_b is not None:
                    path_b = path_b.union(set(to_point_b))
                to_friend_b = self.world.path.get_shortest_path(point_b, closest_friendly_territory, self.friendly_unit.snake)
                if to_friend_b is not None:
                    path_b = path_b.union(set(to_friend_b))

                flood_a = self.world.fill.flood_fill(path_a, self.friendly_unit.territory, closest_friendly_territory, closest_friendly_territory)
                flood_b = self.world.fill.flood_fill(path_b, self.friendly_unit.territory, closest_friendly_territory, closest_friendly_territory)

                if (len(flood_a) / len(path_a) > len(flood_b) / len(path_b)):
                    self.return_midpoint = point_a
                else:
                    self.return_midpoint = point_b

                # print("midpoint: ", self.return_midpoint)

            if self.return_midpoint not in self.friendly_unit.snake:
                next_move = self.world.path.get_shortest_path(position, self.return_midpoint, self.friendly_unit.snake)[0]

            else:
                next_move = self.world.path.get_shortest_path(position, closest_friendly_territory, self.friendly_unit.snake)[0]
                if next_move is self.return_midpoint:
                    self.return_midpoint = None

            self.return_flag = True
            self.targets = []
            # print("Returning")

        else:
            score_array = np.full((28, 28), 1)
            for pos in self.friendly_unit.territory:
                score_array[pos[0] - 1, pos[1] - 1] = 0
            for enemy_unit in self.enemy_units:
                for pos in enemy_unit.territory:
                    score_array[pos[0] - 1, pos[1] - 1] = 5

            search_targets = []

            closest_distance_to_enemy = 1000
            for enemy_unit in self.enemy_units:
                if enemy_unit.turn_penalty == 0:
                    body_to_enemy = self.world.util.get_closest_friendly_body_from(enemy_unit.position, enemy_unit.snake)
                    if body_to_enemy is not None:
                        body_position = body_to_enemy.position
                        distance = abs(body_position[0] - enemy_unit.position[0]) + abs(
                            body_position[1] - enemy_unit.position[1])
                        if distance < closest_distance_to_enemy:
                            closest_distance_to_enemy = distance

            if closest_distance_to_enemy == 1000:
                for enemy_unit in self.enemy_units:
                    if enemy_unit.turn_penalty == 0:
                        distance = self.world.path.get_shortest_path_distance(enemy_unit.position, self.friendly_unit.position)
                        if distance < closest_distance_to_enemy:
                            closest_distance_to_enemy = distance

            closest_friendly_territory = self.world.util.get_closest_friendly_territory_from(position, self.friendly_unit.snake).position

            # 1. find search area
            for i in range(1, 29):
                for j in range(1, 29):     # iterate through every cell
                    if (i, j) not in self.friendly_unit.territory and (i, j) not in self.friendly_unit.snake:
                        # total_distance_through_point = 2 * (abs(self.anchor[0] - i) + abs(self.anchor[1] - j))
                        shyness = 1
                        total_distance_through_point = int(shyness * (abs(position[0] - i) + abs(position[1] - j) + (abs(closest_friendly_territory[0] - i) + abs(closest_friendly_territory[1] - j))))

                        if total_distance_through_point < closest_distance_to_enemy:
                            search_targets.append((i, j))

            # print("done searching")
            # 2. search search area
            biggest_target = None
            biggest_score = 0
            for target in search_targets:
                min_x = min(self.anchor[0], target[0]) - 1
                max_x = max(self.anchor[0], target[0]) - 1
                min_y = min(self.anchor[1], target[1]) - 1
                max_y = max(self.anchor[1], target[1]) - 1

                enemy_body_bonus = 0
                murder_incentive = 500

                for enemy_unit in self.enemy_units:
                    if target in enemy_unit.snake:
                        # print("Enemy body nearby")
                        enemy_body_bonus += murder_incentive

                score = np.sum(score_array[min_x:max_x, min_y:max_y]) + enemy_body_bonus
                if score > biggest_score:
                    biggest_score = score
                    biggest_target = target
            # print("biggest score: ", biggest_score)

            if biggest_target is None:
                friendly_return = self.world.util.get_closest_friendly_territory_from(position, self.friendly_unit.snake).position
                next_move = self.world.path.get_shortest_path(position, friendly_return, self.friendly_unit.snake)[0]
                print("evasive manouevre, heading to friendly ", next_move)
            else:
                # print("target: ", biggest_target)

                # self.targets.append(biggest_target)
                self.targets = [biggest_target]
                next_move = world.path.get_shortest_path(position, biggest_target, self.friendly_unit.snake)[0]
                # print("move: ", next_move)

        if position in self.friendly_unit.territory and next_move not in self.friendly_unit.territory:
            self.anchor = position

        elif position not in self.friendly_unit.territory and next_move in self.friendly_unit.territory:
            self.anchor = None
            self.return_flag = False
            self.return_midpoint = None
            self.targets = []

        # suicide prevention
        if next_move in self.friendly_unit.snake:
            # get any move
            if (position[0] + 1, position[1] + 1) not in self.friendly_unit.snake:
                next_move = (position[0] + 1, position[1] + 1)
            elif (position[0] + 1, position[1] - 1) not in self.friendly_unit.snake:
                next_move = (position[0] + 1, position[1] - 1)
            elif (position[0] - 1, position[1] + 1) not in self.friendly_unit.snake:
                next_move = (position[0] - 1, position[1] + 1)
            else:
                next_move = (position[0] - 1, position[1] - 1)

        friendly_unit.move(next_move)

        # print("Turn {0}: currently at {1}, making {2}".format(
        #     str(self.turn_count),
        #     str(friendly_unit.position)
        # ))

    def get_succ(self, position):
        successors = []

        for move in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            new_position = tuple(map(operator.add, position, move))
            if new_position not in self.friendly_unit.snake and not self.world.is_wall(new_position):
                successors.append(new_position)
        return successors;
