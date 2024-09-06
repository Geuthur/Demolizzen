import random


def get_work_text():
    return random.choice(
        [
            "You enter the office and find an urgent task on your desk.",
            "Your boss calls you into his office and assigns you an important task.",
            "You receive an email with a new task that needs to be completed immediately.",
            "During the team meeting, you are given responsibility for a new project.",
        ]
    )


def get_work2_text():
    return random.choice(
        [
            "You go to your colleague's desk to work together on the task.",
            "During the coffee break, you chat with a colleague about the upcoming task.",
            "You ask an experienced colleague for advice on solving the task.",
            "Your team collaborates to efficiently handle the task.",
        ]
    )


def get_work_end_text():
    return random.choice(
        [
            "You have successfully mastered the work task and feel satisfied with your day. \nIt was a productive workday, and you leave the office with a smile on your face. \n\nYour earnings are:",
            "The task was challenging, but you completed it successfully. \nYour colleagues applaud you, and you go home with pride. \n\nYour earnings are:",
            "It was a tough workday, but you conquered the task. \nAs you leave the office, you feel exhausted but content. \n\nYour earnings are:",
            "Despite some challenges, you handled the task with flying colors. \nYour boss praises your hard work, and you leave the office with a sense of fulfillment. \n\nYour earnings are:",
        ]
    )


def get_work_bonus_text():
    return random.choice(
        [
            "While working on the task, you find a hidden shortcut that saves time.",
            "A colleague surprises you with a delicious coffee that boosts your productivity.",
            "You discover a forgotten drawer full of useful office supplies.",
            "Thanks to a clever idea from you, the task is completed faster than expected.",
        ]
    )
