

def main():
    import cmd_queue
    import ubelt as ub
    queue = cmd_queue.Queue.create(backend='slurm', partition='project123',
                                   account='user123', ntasks=1)

    job1 = queue.submit(ub.codeblock(
        '''
        command1 --input=foo.txt --output=bar.txt
        '''))

    job2 = queue.submit(ub.codeblock(
        '''
        command2 --input=foo.txt --output=baz.txt
        '''))

    queue.submit(ub.codeblock(
        '''
        command3 --input1=bar.txt --input2=baz.txt --output=buz.txt
        '''), depends=[job2, job1])

    queue.print_commands()

    queue.run()
