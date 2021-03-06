from datetime import datetime, timedelta
from threading import Thread
from util.logger import Logger
from util.utils import Region, Utils


class CombatModule(object):

    def __init__(self, config, stats):
        """Initializes the Combat module.

        Args:
            config (Config): ALAuto Config instance.
            stats (Stats): ALAuto Stats instance.
        """
        self.enabled = True
        self.config = config
        self.stats = stats
        self.morale = {}
        self.next_combat_time = datetime.now()
        self.resume_previous_sortie = False
        self.kills_needed = 0
        self.combat_auto_enabled = False
        self.hard_mode = self.config.combat['hard_mode']
        self.sortie_map = self.config.combat['map']
        self.event_map = self.sortie_map.split('-')[0] == 'E'
        self.need_to_refocus = True
        self.avoided_ambush = True
        self.region = {
            'nav_back': Region(12, 8, 45, 30),
            'home_menu_attack': Region(1000, 365, 180, 60),
            'event_map': Region(1145, 140, 70, 40),
            'map_go_1': Region(875, 465, 115, 35),
            'map_go_2': Region(925, 485, 170, 45),
            'battle_start': Region(1000, 610, 125, 50),
            'toggle_autobattle': Region(150, 80, 65, 20),
            'switch_fleet': Region(850, 650, 180, 40)
        }

    def combat_logic_wrapper(self):
        """Method that fires off the necessary child methods that encapsulates
        the entire action of sortieing combat fleets and resolving combat.

        Returns:
            bool: True if the combat cycle was complete
        """
        if self.check_need_to_sortie():
            Logger.log_msg('Navigating to map.')
            Utils.touch_randomly(self.region['home_menu_attack'])
            Utils.script_sleep(1)
            if not self.resume_previous_sortie:
                self.kills_needed = self.config.combat['kills_needed']
                if self.event_map:
                    Utils.touch_randomly(self.region['event_map'])
                if self.hard_mode:
                    Utils.find_and_touch('map_menu_hard')
                Utils.wait_and_touch('map_{}'.format(self.sortie_map), 5, 0.85)
                Utils.script_sleep()
                Utils.touch_randomly(self.region['map_go_1'])
                Utils.script_sleep()
                Utils.touch_randomly(self.region['map_go_2'])
                Utils.script_sleep(5)
                if self.config.combat['alt_clear_fleet']:
                    Logger.log_msg('Alternate clearing fleet enabled, ' +
                                   'switching to 2nd fleet to clear trash')
                    self.switch_fleet()
                    self.need_to_refocus = False
            # Trash
            if self.clear_trash():
                # Boss
                if self.config.combat['boss_fleet']:
                    Logger.log_msg('Switching to 2nd fleet to kill boss')
                    self.switch_fleet()
                self.clear_boss()
                self.stats.increment_combat_done()
                self.next_combat_time = datetime.now()
                Logger.log_success('Sortie complete. Navigating back home.')
                while not (Utils.exists('home_menu_build')):
                    Utils.touch_randomly(self.region['nav_back'])
                self.set_next_combat_time({'seconds': 10})
            return True
        return False

    def check_need_to_sortie(self):
        """Method to check whether the combat fleets need to sortie based on
        the stored next combat time.

        Returns:
            bool: True if the combat fleets need to sortie, False otherwise
        """
        if not self.enabled:
            return False
        if self.next_combat_time < datetime.now():
            return True
        return False

    def set_next_combat_time(self, delta={}):
        """Method to set the next combat time based on the provided hours,
        minutes, and seconds delta.

        Args:
            delta (dict, optional): Dict containing the hours, minutes, and
                seconds delta.
        """
        self.next_combat_time = datetime.now() + timedelta(
            hours=delta['hours'] if 'hours' in delta else 0,
            minutes=delta['minutes'] if 'minutes' in delta else 0,
            seconds=delta['seconds'] if 'seconds' in delta else 0)

    def get_fleet_location(self):
        """Method to get the fleet's current location. Note it uses the green
        fleet marker to find the location but returns around the area of the
        feet of the flagship

        Returns:
            array: An array containing the x and y coordinates of the fleet's
            current location.
        """
        coords = None
        similarity = 0.9
        while coords is None:
            coords = Utils.find('combat_fleet_marker', similarity)
            similarity -= 0.01
        return [coords.x + 10, coords.y + 175]

    def get_closest_enemy(self, blacklist=[]):
        """Method to get the enemy closest to the fleet's current location. Note
        this will not always be the enemy that is actually closest due to the
        asset used to find enemies and when enemies are obstructed by terrain
        or the second fleet

        Args:
            blacklist(array, optional): Defaults to []. An array of
            coordinates to exclude when searching for the closest enemy

        Returns:
            array: An array containing the x and y coordinates of the closest
            enemy to the fleet's current location
        """
        x_dist = 125
        y_dist = 175
        swipes = [['n', 1.0], ['e', 1.0], ['s', 1.5], ['w', 1.5]]
        closest = None
        while closest is None:
            if self.need_to_refocus:
                self.refocus_fleet()
            current_location = self.get_fleet_location()
            for swipe in swipes:
                enemies = Utils.find_all('combat_enemy_fleet', 0.88)
                if enemies:
                    for coord in blacklist:
                        enemies.remove(coord)
                    Logger.log_msg('Current location is: {}'
                                   .format(current_location))
                    Logger.log_msg('Enemies found at: {}'.format(enemies))
                    closest = enemies[Utils.find_closest(
                                      enemies, current_location)[1]]
                    Logger.log_msg('Closest enemy is at {}'.format(closest))
                    return [closest[0], closest[1] - 10]
                else:
                    direction, multiplier = swipe[0], swipe[1]
                    if direction == 'n':
                        current_location[1] = (
                            current_location[1] + (2 * y_dist * multiplier))
                        Utils.swipe(640, 360 - y_dist * multiplier,
                                    640, 360 + y_dist * multiplier, 250)
                    elif direction == 's':
                        current_location[1] = (
                            current_location[1] - (2 * y_dist * multiplier))
                        Utils.swipe(640, 360 + y_dist * multiplier,
                                    640, 360 - y_dist * multiplier, 250)
                    elif direction == 'e':
                        current_location[0] = (
                            current_location[0] + (2 * x_dist * multiplier))
                        Utils.swipe(640 + x_dist * multiplier, 360,
                                    640 - x_dist * multiplier, 360, 250)
                    elif direction == 'w':
                        current_location[0] = (
                            current_location[0] - (2 * x_dist * multiplier))
                        Utils.swipe(640 - x_dist * multiplier, 360,
                                    640 + x_dist * multiplier, 360, 250)
                self.need_to_refocus = True
            x_dist *= 1.5
            y_dist *= 1.5
        return None

    def conduct_prebattle_check(self):
        """Method to check morale and check if auto-battle is enabled before a
        sortie. Enables autobattle if not already enabled.

        Returns:
            bool: True if it is ok to proceed with the battle
        """
        ok = True
        fleet_morale = self.check_morale()
        if fleet_morale['sad']:
            self.set_next_combat_time({'hours': 2})
            ok = False
        elif fleet_morale['neutral']:
            self.set_next_combat_time({'hours': 1})
            ok = False
        else:
            if not self.combat_auto_enabled:
                Logger.log_msg('Checking if auto-battle is enabled.')
                if not Utils.exists('combat_auto_enabled'):
                    Logger.log_msg('Enabling auto-battle')
                    Utils.touch_randomly(self.region['toggle_autobattle'])
                    Utils.script_sleep(0.5)
                    Utils.touch_randomly(Region(600, 100, 150, 150))
                    Utils.script_sleep(2)
                self.combat_auto_enabled = True
        return ok

    def conduct_battle(self):
        """Method to start the battle and click through the rewards once the
        battle is complete.
        """
        Logger.log_msg('Starting battle')
        while (Utils.exists('combat_auto_enabled')):
            Utils.touch_randomly(self.region['battle_start'])
            if Utils.wait_for_exist('combat_notification_sort', 3):
                return False
        Utils.script_sleep(30)
        while not Utils.find_and_touch('combat_battle_confirm', 0.85):
            if Utils.find_and_touch('confirm'):
                Logger.log_msg('Locked new ship.')
            else:
                Utils.touch_randomly(Region(0, 100, 150, 150))
                Utils.script_sleep()
        Logger.log_msg('Battle complete.')
        if Utils.wait_and_touch('confirm', 3):
            Logger.log_msg('Dismissing urgent notification.')
        return True

    def clear_trash(self):
        """Finds trash mobs closest to the current fleet location and battles
        them until the boss spawns
        """
        while self.kills_needed > 0:
            blacklist = []
            tries = 0
            if self.resume_previous_sortie:
                self.resume_previous_sortie = False
                Utils.find_and_touch('combat_attack')
                Utils.script_sleep(2)
            else:
                self.avoided_ambush = True
            while not Utils.exists('combat_battle_start'):
                if Utils.find_and_touch('combat_evade'):
                    if Utils.wait_for_exist('combat_battle_start', 3):
                        self.avoided_ambush = False
                    else:
                        Logger.log_msg('Successfully avoided ambush.')
                elif Utils.find_and_touch('combat_items_received'):
                    pass
                else:
                    enemy_coord = self.get_closest_enemy()
                    if tries > 2:
                        blacklist.append(enemy_coord)
                        enemy_coord = self.get_closest_enemy(blacklist)
                    Logger.log_msg('Navigating to enemy fleet at {}'
                                   .format(enemy_coord))
                    Utils.touch(enemy_coord)
                    tries += 1
                    Utils.script_sleep(5)
            if self.conduct_prebattle_check():
                if self.conduct_battle():
                    self.need_to_refocus = True
                else:
                    self.resume_previous_sortie = True
                    while not (Utils.exists('home_menu_build')):
                        Utils.touch_randomly(self.region['nav_back'])
                    # Add logic for retirement here?
                    return False
            if self.avoided_ambush:
                self.kills_needed -= 1
            Logger.log_msg('Kills left for boss to spawn: {}'
                           .format(self.kills_needed))
        Utils.script_sleep(1)
        return True

    def clear_boss(self):
        """Finds the boss and battles it
        """
        while not Utils.exists('combat_battle_start'):
            boss = None
            similarity = 0.8
            while boss is None:
                boss = Utils.scroll_find(
                    'combat_enemy_boss_alt', 250, 175, similarity)
                similarity -= 0.015
            Logger.log_msg('Boss found at: {}'.format([boss.x, boss.y]))
            Logger.log_msg('Focusing on boss')
            Utils.swipe(boss.x, boss.y, 640, 360, 250)
            boss = None
            while boss is None:
                boss = Utils.find('combat_enemy_boss_alt', similarity)
                similarity -= 0.015
            # Click slightly above boss to be able to click on it in case
            # the boss is obstructed by another fleet or enemy
            boss_coords = [boss.x + 50, boss.y - 15]
            Utils.touch(boss_coords)
            if Utils.wait_for_exist('combat_unable', 3):
                boss = Utils.scroll_find('combat_enemy_boss_alt',
                                         250, 175, 0.75)
                enemies = Utils.find_all('combat_enemy_fleet', 0.89)
                enemies.remove(boss)
                closest_to_boss = enemies[Utils.find_closest(enemies, boss)[1]]
                Utils.find_and_touch(closest_to_boss)
                if Utils.wait_for_exist('combat_unable', 3):
                    Utils.find_and_touch(self.get_closest_enemy())
                    if Utils.wait_for_exist('combat_battle_start', 3):
                        self.conduct_battle()
            else:
                Utils.script_sleep(5)
                if Utils.find_and_touch('combat_evade'):
                    if Utils.wait_for_exist('combat_battle_start', 3):
                        self.conduct_battle()
                        self.refocus_fleet()
                elif Utils.find_and_touch('combat_items_received'):
                    pass
        if self.conduct_prebattle_check():
            self.conduct_battle()

    def switch_fleet(self):
        """Method to switch the current fleet
        """
        Utils.touch_randomly(self.region['switch_fleet'])

    def refocus_fleet(self):
        """Method to refocus on the current fleet
        """
        Logger.log_msg('Refocusing fleet.')
        self.switch_fleet()
        Utils.script_sleep(2)
        self.switch_fleet()

    def check_morale(self):
        """Method to multithread the detection of morale states of the fleet.

        Returns:
            dict: dict of bools of the different morale states
        """
        thread_check_neutral_morale = Thread(
            target=self.check_morale_func, args=('neutral',))
        thread_check_sad_morale = Thread(
            target=self.check_morale_func, args=('sad',))
        Utils.multithreader([
            thread_check_neutral_morale, thread_check_sad_morale])
        return self.morale

    def check_morale_func(self, status):
        """Child multithreaded method for checking morale states.

        Args:
            status (string): which morale status to check for
        """
        self.morale[status] = (
            True
            if (Utils.exists('morale_{}'.format(status)))
            else False)
