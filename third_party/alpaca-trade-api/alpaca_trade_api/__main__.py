import argparse
from .rest import REST


def run(args):
    api = REST(**args)
    try:
        from IPython import embed
        embed()
    except ImportError:
        import code
        code.interact(local=locals())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--key-id', help='APCA_API_KEY_ID')
    parser.add_argument('--secret-key', help='APCA_API_SECRET_KEY')
    parser.add_argument('--base-url')
    args = parser.parse_args()

    run({k: v for k, v in vars(args).items() if v is not None})


if __name__ == '__main__':
    main()
