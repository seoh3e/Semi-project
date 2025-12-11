from app.main_demo_telegram import (
    run_RansomFeedNews_demo,
    run_ctifeeds_demo,
    run_hackmanac_cybernews_demo,
    run_venarix_demo,
)

if __name__ == "__main__":
    print("\n[RUN] RansomFeedNews demo")
    run_RansomFeedNews_demo()

    print("\n[RUN] ctifeeds demo")
    run_ctifeeds_demo()

    print("\n[RUN] hackmanac_cybernews demo")
    run_hackmanac_cybernews_demo()

    print("\n[RUN] venarix demo")
    run_venarix_demo()

    print("\n[DONE] all demos\n")



