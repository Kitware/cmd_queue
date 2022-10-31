def test_mixed_hardware():
    """
    We want to have a queue where some processes rely on a GPU, but others
    don't, and be able to run at most N GPU tree_jobs, but have up to M non-GPU
    tree_jobs.
    """

    import cmd_queue
    import ubelt as ub
    backend = 'tmux'

    gres = [0, 1]

    dpath = ub.Path.appdir('cmd_queue', 'tests', 'test_mixed_hardware')

    environ = {}
    queue = cmd_queue.Queue.create(backend, name='test_mixed_hardware',
                                   size=2, environ=environ,
                                   dpath=dpath, gres=gres)

    import itertools as it
    counter = it.count(0)

    def submit_tree(queue, need_pred_pxl=True):
        index = next(counter)
        if need_pred_pxl:
            pred_pxl_job = queue.submit('echo "pred_pxl: $CUDA_VISIBLE_DEVICES"', name=f'pred_pxl_{index}', depends=None, cpus=5, gpus=1)
        else:
            pred_pxl_job = None
        queue.submit('echo "eval_pxl: $CUDA_VISIBLE_DEVICES"', name=f'eval_pxl_{index}', depends=pred_pxl_job, cpus=2)
        queue.submit('echo "pred_trk: $CUDA_VISIBLE_DEVICES"', name=f'pred_trk_{index}', depends=pred_pxl_job, cpus=2)
        queue.submit('echo "eval_trk: $CUDA_VISIBLE_DEVICES"', name=f'eval_trk_{index}', depends=f'pred_trk_{index}', cpus=2)
        queue.submit('echo "pred_act: $CUDA_VISIBLE_DEVICES"', name=f'pred_act_{index}', depends=pred_pxl_job, cpus=2)
        queue.submit('echo "eval_act: $CUDA_VISIBLE_DEVICES"', name=f'eval_act_{index}', depends=f'pred_act_{index}', cpus=2)

    submit_tree(queue)
    submit_tree(queue)
    submit_tree(queue)
    submit_tree(queue)
    submit_tree(queue, False)
    submit_tree(queue, False)

    queue.rprint(with_rich=1)
    queue.write_network_text()

    self = queue
