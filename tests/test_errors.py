
def test_failures_on_each_backend():
    # Test case where a job fails
    import cmd_queue
    backends = cmd_queue.Queue.available_backends()
    for backend in backends:
        self = cmd_queue.Queue.create(backend=backend)
        job1 = self.submit('echo "job1 fails" && false')
        job2 = self.submit('echo "job2 never runs"', depends=[job1])
        job3 = self.submit('echo "job3 never runs"', depends=[job2])
        job4 = self.submit('echo "job4 passes" && true')
        job5 = self.submit('echo "job5 fails" && false', depends=[job4])
        job6 = self.submit('echo "job6 never runs"', depends=[job5])
        job7 = self.submit('echo "job7 never runs"', depends=[job4, job2])
        job8 = self.submit('echo "job8 never runs"', depends=[job4, job1])
        self.print_commands()
        self.run()
        self.read_state()


if __name__ == '__main__':
    """
    CommandLine:
        python ~/code/cmd_queue/tests/test_errors.py
    """
    test_failures_on_each_backend()
