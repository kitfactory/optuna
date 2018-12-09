import lightgbm as lgb
import pytest
from functools import partial

import optuna
from optuna.integration.lightgbm import LightGBMPruningCallback
from optuna.testing.integration import DeterministicPruner


def test_lightgbm_pruning_callback_call():
    # type: () -> None

    env = lgb.callback.CallbackEnv(
        model='test',
        params={},
        begin_iteration=0,
        end_iteration=1,
        iteration=1,
        evaluation_result_list=[('validation', 'binary_error', 1., False)])
    
    env_cv = lgb.callback.CallbackEnv(
        model='test',
        params={},
        begin_iteration=0,
        end_iteration=1,
        iteration=1,
        evaluation_result_list=[(('cv_agg', 'binary_error', 1., False, 1.))])

    # The pruner is deactivated.
    study = optuna.create_study(pruner=DeterministicPruner(False))
    trial = study._run_trial(func=lambda _: 1.0, catch=(Exception,))
    pruning_callback = LightGBMPruningCallback(trial, 'binary_error', valid_name='validation')
    pruning_callback(env)
    pruning_callback(env_cv)

    # The pruner is activated.
    study = optuna.create_study(pruner=DeterministicPruner(True))
    trial = study._run_trial(func=lambda _: 1.0, catch=(Exception,))
    pruning_callback = LightGBMPruningCallback(trial, 'binary_error', valid_name='validation')
    with pytest.raises(optuna.structs.TrialPruned):
        pruning_callback(env)
        pruning_callback(env_cv)

test_lightgbm_pruning_callback_call()
def test_lightgbm_pruning_callback():
    # type: () -> None

    study = optuna.create_study(pruner=DeterministicPruner(True))
    study.optimize(objective, n_trials=1)
    assert study.trials[0].state == optuna.structs.TrialState.PRUNED
    study.optimize(partial(objective, cv=True), n_trials=1)
    assert study.trials[0].state == optuna.structs.TrialState.PRUNED

    study = optuna.create_study(pruner=DeterministicPruner(False))
    study.optimize(objective, n_trials=1)
    assert study.trials[0].state == optuna.structs.TrialState.COMPLETE
    assert study.trials[0].value == 1.
    study.optimize(partial(objective, cv=True), n_trials=1)
    assert study.trials[0].state == optuna.structs.TrialState.COMPLETE
    assert study.trials[0].value == 1.

    # Use non default validation name.
    custom_valid_name = 'my_validation'
    study = optuna.create_study(pruner=DeterministicPruner(False))
    study.optimize(lambda trial: objective(trial, valid_name=custom_valid_name), n_trials=1)
    assert study.trials[0].state == optuna.structs.TrialState.COMPLETE
    assert study.trials[0].value == 1.
    study.optimize(lambda trial: objective(trial, valid_name=custom_valid_name, cv=True), n_trials=1)
    assert study.trials[0].state == optuna.structs.TrialState.COMPLETE
    assert study.trials[0].value == 1.


def test_lightgbm_pruning_callback_errors():
    # type: () -> None

    # "maximize" direction isn't supported yet.
    study = optuna.create_study(pruner=DeterministicPruner(False))
    with pytest.raises(ValueError):
        study.optimize(lambda trial: objective(trial, metric='auc'), n_trials=1, catch=())
        study.optimize(lambda trial: objective(trial, metric='auc', cv=True), n_trials=1, catch=())

    # Unknown metric
    study = optuna.create_study(pruner=DeterministicPruner(False))
    with pytest.raises(ValueError):
        study.optimize(lambda trial: objective(trial, metric='foo_metric'), n_trials=1, catch=())
        study.optimize(lambda trial: objective(trial, metric='foo_metric', cv=True), n_trials=1, catch=())

    # Unknown validation name
    study = optuna.create_study(pruner=DeterministicPruner(False))
    with pytest.raises(ValueError):
        study.optimize(lambda trial: objective(trial, valid_name='valid_1',
                                force_default_valid_names=True),
                       n_trials=1, catch=())
        study.optimize(lambda trial: objective(trial, valid_name='valid_1',
                                force_default_valid_names=True, cv=True),
        n_trials=1, catch=())


def objective(trial, metric='binary_error', valid_name='valid_0', force_default_valid_names=False, cv=False):
    # type: (optuna.trial.Trial, str, str, bool) -> float

    dtrain = lgb.Dataset([[1.]], label=[1.])
    dtest = lgb.Dataset([[1.]], label=[1.])

    if force_default_valid_names:
        valid_names = None
    else:
        valid_names = [valid_name]

    pruning_callback = LightGBMPruningCallback(trial, metric, valid_name=valid_name)
    if cv:
        lgb.cv({'objective': 'binary', 'metric': ['auc', 'binary_error']}, dtrain, 1,
              verbose_eval=False, callbacks=[pruning_callback])
    elif not cv:
        lgb.train({'objective': 'binary', 'metric': ['auc', 'binary_error']}, dtrain, 1,
                valid_sets=[dtest], valid_names=valid_names,
                verbose_eval=False, callbacks=[pruning_callback])
    return 1.0
