# Copyright 2020-2021, Optimizely
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import copy

from .project_config import ProjectConfig
import logging


class OptimizelyConfig(object):
    def __init__(self, revision, experiments_map, features_map, datafile=None,
                 sdk_key=None, environment_key=None, attributes=None, events=None, audiences=None):
        self.revision = revision
        self.experiments_map = experiments_map
        self.features_map = features_map
        self._datafile = datafile
        self.sdk_key = sdk_key or ''
        self.environment_key = environment_key or ''
        self.attributes = attributes or []
        self.events = events or []
        self.audiences = audiences or []

    def get_datafile(self):
        """ Get the datafile associated with OptimizelyConfig.

        Returns:
            A JSON string representation of the environment's datafile.
        """
        return self._datafile

    def get_sdk_key(self):
        """ Get the sdk key associated with OptimizelyConfig.

        Returns:
            A string containing sdk key.
        """
        return self.sdk_key

    def get_environment_key(self):
        """ Get the environemnt key associated with OptimizelyConfig.

        Returns:
            A string containing environment key.
        """
        return self.environment_key

    def get_attributes(self):
        """ Get the attributes associated with OptimizelyConfig

        returns:
            A list of attributes.
        """
        return self.attributes

    def get_events(self):
        """ Get the events associated with OptimizelyConfig

        returns:
            A list of events.
        """
        return self.events


class OptimizelyExperiment(object):
    def __init__(self, id, key, variations_map, audiences):
        self.id = id
        self.key = key
        self.audiences = audiences
        self.variations_map = variations_map


class OptimizelyFeature(object):
    def __init__(self, id, key, experiments_map, variables_map, experiment_rules, delivery_rules):
        self.id = id
        self.key = key
        self.experimentRules = experiment_rules or []
        self.deliveryRules = delivery_rules or []
        self.experiments_map = experiments_map
        self.variables_map = variables_map


class OptimizelyVariation(object):
    def __init__(self, id, key, feature_enabled, variables_map):
        self.id = id
        self.key = key
        self.feature_enabled = feature_enabled
        self.variables_map = variables_map


class OptimizelyVariable(object):
    def __init__(self, id, key, variable_type, value):
        self.id = id
        self.key = key
        self.type = variable_type
        self.value = value


class OptimizelyAttribute(object):
    def __init__(self, id, key):
        self.id = id
        self.key = key


class OptimizelyAudience(object):
    def __init__(self, id, name, conditions):
        self.id = id
        self.name = name
        self.conditions = conditions


class OptimizelyEvent(object):
    def __init__(self, id, key, experiment_ids):
        self.id = id
        self.key = key
        self.experimentIds = experiment_ids


class OptimizelyConfigService(object):
    """ Class encapsulating methods to be used in creating instance of OptimizelyConfig. """

    def __init__(self, project_config):
        """
        Args:
            project_config ProjectConfig
        """
        self.is_valid = True

        if not isinstance(project_config, ProjectConfig):
            self.is_valid = False
            return

        self._datafile = project_config.to_datafile()
        self.experiments = project_config.experiments
        self.feature_flags = project_config.feature_flags
        self.groups = project_config.groups
        self.revision = project_config.revision
        self.sdk_key = project_config.sdk_key
        self.environment_key = project_config.environment_key
        self.attributes = project_config.attributes
        self.events = project_config.events
        self.audiences = project_config.audiences
        self.audience_id_map = project_config.audience_id_map
        self.roll_out_id_map = project_config.rollout_id_map
        self.typed_audiences = project_config.typed_audiences
        self._create_lookup_maps()

    def get_config(self):
        """ Gets instance of OptimizelyConfig

        Returns:
            Optimizely Config instance or None if OptimizelyConfigService is invalid.
        """

        if not self.is_valid:
            return None

        experiments_key_map, experiments_id_map = self._get_experiments_maps()
        features_map = self._get_features_map(experiments_id_map)
        audiences = self._get_config_audiences()
        attributes = [OptimizelyAttribute(**attribute) for attribute in self.attributes]
        events = self._get_config_events()

        return OptimizelyConfig(
            self.revision,
            experiments_key_map,
            features_map,
            self._datafile,
            self.sdk_key,
            self.environment_key,
            attributes,
            events,
            audiences)

    def _get_config_audiences(self):
        """ get audiences for optimizelyConfig object.

        Returns:
            list -- audiences list of unique typed audiences and audiences
        """
        global_audiences = [audience for audience in self.typed_audiences if audience['id']]

        filtered_audience = [audience for audience in self.audiences if
                             audience['id'] not in [t_audience['id'] for t_audience in global_audiences]]

        global_audiences = global_audiences + filtered_audience
        audiences = [OptimizelyAudience(audience['id'], audience['name'], audience['conditions']) for audience in
                     global_audiences if audience['id'] != '$opt_dummy_audience']
        return audiences

    def _get_config_events(self):
        """ get events for optimizelyConfig object.

        Returns:
            list -- list of all events as OptimizelyEvent
        """
        events = [OptimizelyEvent(event['id'], event['key'], event['experimentIds']) for event in self.events]
        return events

    def _create_lookup_maps(self):
        """ Creates lookup maps to avoid redundant iteration of config objects.  """

        self.exp_id_to_feature_map = {}
        self.feature_key_variable_key_to_variable_map = {}
        self.feature_key_variable_id_to_variable_map = {}

        for feature in self.feature_flags:
            for experiment_id in feature['experimentIds']:
                self.exp_id_to_feature_map[experiment_id] = feature

            variables_key_map = {}
            variables_id_map = {}
            for variable in feature.get('variables', []):
                opt_variable = OptimizelyVariable(
                    variable['id'], variable['key'], variable['type'], variable['defaultValue']
                )
                variables_key_map[variable['key']] = opt_variable
                variables_id_map[variable['id']] = opt_variable

            self.feature_key_variable_key_to_variable_map[feature['key']] = variables_key_map
            self.feature_key_variable_id_to_variable_map[feature['key']] = variables_id_map

    def _get_variables_map(self, experiment, variation):
        """ Gets variables map for given experiment and variation.

        Args:
            experiment dict -- Experiment parsed from the datafile.
            variation dict -- Variation of the given experiment.

        Returns:
            dict - Map of variable key to OptimizelyVariable for the given variation.
        """
        feature_flag = self.exp_id_to_feature_map.get(experiment['id'], None)
        if feature_flag is None:
            return {}

        # set default variables for each variation
        variables_map = {}
        variables_map = copy.deepcopy(self.feature_key_variable_key_to_variable_map[feature_flag['key']])

        # set variation specific variable value if any
        if variation.get('featureEnabled'):
            for variable in variation.get('variables', []):
                feature_variable = self.feature_key_variable_id_to_variable_map[feature_flag['key']][variable['id']]
                variables_map[feature_variable.key].value = variable['value']

        return variables_map

    def _get_variations_map(self, experiment):
        """ Gets variation map for the given experiment.

        Args:
            experiment dict -- Experiment parsed from the datafile.

        Returns:
            dict -- Map of variation key to OptimizelyVariation.
        """
        variations_map = {}

        for variation in experiment.get('variations', []):
            variables_map = self._get_variables_map(experiment, variation)
            feature_enabled = variation.get('featureEnabled', None)

            optly_variation = OptimizelyVariation(
                variation['id'], variation['key'], feature_enabled, variables_map
            )

            variations_map[variation['key']] = optly_variation

        return variations_map

    def _get_all_experiments(self):
        """ Gets all experiments in the project config.

        Returns:
            list -- List of dicts of experiments.
        """
        experiments = self.experiments

        for group in self.groups:
            experiments = experiments + group['experiments']

        return experiments

    def _get_experiment_audiences(self, experiment_audience_condition, project_config_audience_id_map):
        """ get the audience conditions of an experiment  mapped to a string.

        Args:
            experiment_audience_condition -- audience conditions list of an experiment
            project_config_audience_id_map -- audience id map for getting audience names
        Returns:
            string -- string containing audience conditions map to audience names
        """
        result_audience = ""
        if experiment_audience_condition:  # checking if audience condition is not None or empty
            cond = ""  # initialising a condition string
            for item in experiment_audience_condition:
                sub_audiences = ""  # initialising a string to get result_audience if nested conditions
                if type(item) == list:  # checking type of item if a list call a recursive call
                    sub_audiences = self._get_experiment_audiences(item, project_config_audience_id_map)
                    sub_audiences = "(" + sub_audiences + ")"
                elif item in ["and", "or", "not"]:  # checking if item is one of the
                    # conditions to place accordingly
                    cond = str(item).upper()
                else:
                    item_str = str(item)
                    if result_audience != "" or cond == "NOT":  # checking that result
                        # audience is not empty to place not condition at start
                        if result_audience:  # in case result_audience is not
                            # empty append an empty space to match format
                            result_audience = result_audience + " "
                        else:
                            result_audience = result_audience
                        if cond:  # checking if condition is not empty to
                            # handle the case if no condition then place OR between them
                            cond = cond
                        else:
                            cond = "OR"
                        try:  # if not a name of audience id found in
                            # audience_id map then using the audience id
                            result_audience = result_audience + cond + " \"" + project_config_audience_id_map[
                                item_str].name + "\""
                        except Exception as ex:
                            result_audience = result_audience + cond + " \"" + item_str + "\""
                            logging.exception(ex)
                    else:  # in case result_audience is not null then place that audience id accordingly
                        try:
                            result_audience = "\"" + project_config_audience_id_map[item_str].name + "\""
                        except Exception as ex:
                            result_audience = "\"" + item_str + "\""
                            logging.exception(ex)

                if str(sub_audiences) != "":  # to handle the nested result_audience
                    if result_audience != "" or cond == "NOT":
                        if result_audience:
                            result_audience = result_audience + " "
                        else:
                            result_audience = result_audience
                        if cond:
                            cond = cond
                        else:
                            cond = "OR"
                        result_audience = result_audience + cond + " " + sub_audiences
                    else:
                        result_audience = result_audience + sub_audiences
        return result_audience

    def _get_experiments_maps(self):
        """ Gets maps for all the experiments in the project config.

        Returns:
            dict, dict -- experiment key/id to OptimizelyExperiment maps.
        """
        # Key map is required for the OptimizelyConfig response.
        experiments_key_map = {}
        # Id map comes in handy to figure out feature experiment.
        experiments_id_map = {}

        all_experiments = self._get_all_experiments()
        for exp in all_experiments:
            audiences = ''
            if 'audienceConditions' in exp.keys():
                audiences = self._get_experiment_audiences(exp['audienceConditions'], self.audience_id_map)
            optly_exp = OptimizelyExperiment(
                exp['id'], exp['key'], self._get_variations_map(exp), audiences
            )
            experiments_key_map[exp['key']] = optly_exp
            experiments_id_map[exp['id']] = optly_exp
        return experiments_key_map, experiments_id_map

    def _get_delivery_rules(self, rollout_id, roll_out_id_map, audience_id_map):
        """ get delivery rules for optimizelyFeature.

        Args:
            rollout_id -- feature rollout id for getting rollout
            rollout_id_map -- roll out id map to pick rollout experiments for delivery rules
            audience_id_map -- map for getting audiences of rollout experiment
        Returns:
            list -- OptimizelyExperiments as delivery rules
        """

        delivery_rules = []
        rollout = roll_out_id_map[rollout_id]
        experiments = rollout.experiments
        for exp in experiments:
            audiences = ''
            if 'audienceConditions' in exp.keys():
                audiences = self._get_experiment_audiences(exp['audienceConditions'], audience_id_map)
            optly_exp = OptimizelyExperiment(
                exp['id'], exp['key'], self._get_variations_map(exp),  audiences
            )
            delivery_rules.append(optly_exp)
        return delivery_rules

    def _get_features_map(self, experiments_id_map):
        """ Gets features map for the project config.

        Args:
            experiments_id_map dict -- experiment id to OptimizelyExperiment map
            rollout_id_map -- roll out id map to pick rollout experiments for delivery rules
            audience_id_map -- map for getting audiences of rollout experiment

        Returns:
            dict -- feaure key to OptimizelyFeature map
        """
        features_map = {}

        for feature in self.feature_flags:
            exp_map = {}
            experiment_rules = []
            delivery_rules = []
            if 'rolloutId' in feature.keys() and  feature['rolloutId'] != '':
                rollout_id = feature['rolloutId']
                delivery_rules = self._get_delivery_rules(rollout_id, self.roll_out_id_map, self.audience_id_map)
            for experiment_id in feature.get('experimentIds', []):
                optly_exp = experiments_id_map[experiment_id]
                experiment_rules.append(optly_exp)
                exp_map[optly_exp.key] = optly_exp

            variables_map = self.feature_key_variable_key_to_variable_map[feature['key']]

            optly_feature = OptimizelyFeature(
                feature['id'], feature['key'], exp_map, variables_map, experiment_rules, delivery_rules
            )

            features_map[feature['key']] = optly_feature

        return features_map
