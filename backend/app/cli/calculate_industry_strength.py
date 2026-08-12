import argparse
from datetime import date, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.settings import get_settings
from app.services.industry_strength_calculation import IndustryStrengthCalculationService


def run_sync(date_str: str | None, from_date_str: str | None, to_date_str: str | None) -> None:
    settings = get_settings()
    sync_url = settings.database_url.replace("+asyncpg", "").replace("+psycopg", "")
    engine = create_engine(sync_url)
    Session = sessionmaker(bind=engine)

    with Session() as session:
        calc_service = IndustryStrengthCalculationService(session)

        if from_date_str and to_date_str:
            curr = date.fromisoformat(from_date_str)
            end = date.fromisoformat(to_date_str)
            tot_ins = 0
            tot_upd = 0
            while curr <= end:
                res = calc_service.calculate_for_date(curr)
                tot_ins += res["inserted"]
                tot_upd += res["updated"]
                curr += timedelta(days=1)
            print(f"Calculated strength range {from_date_str} to {to_date_str}: inserted={tot_ins}, updated={tot_upd}")
        else:
            target_d = date.fromisoformat(date_str) if date_str else date.today()
            res = calc_service.calculate_for_date(target_d)
            print(f"Calculated strength for {target_d}: inserted={res['inserted']}, updated={res['updated']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Calculate Industry & Theme Strength Snapshots")
    parser.add_argument("--date", help="YYYY-MM-DD target date")
    parser.add_argument("--from-date", help="YYYY-MM-DD range start")
    parser.add_argument("--to-date", help="YYYY-MM-DD range end")
    args = parser.parse_args()
    run_sync(args.date, args.from_date, args.to_date)


if __name__ == "__main__":
    main()
