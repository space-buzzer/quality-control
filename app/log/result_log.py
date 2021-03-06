# ResultLog -- collects results for a run and handle printing/posting them
#
# Each message is assigned a category
#
#   message_id is optional.  if set, the messages are consolidated into single line if than 10 of them.
#
from enum import Enum
import json
import io
import pandas as pd
import numpy as np
from typing import Tuple, Dict, List
import time
import html

from app.util import udatetime

class ResultCategory(Enum):
    DATA_QUALITY = "data quality"
    DATA_SOURCE = "data source"
    DATA_ENTRY = "data entry"
    INTERNAL = "internal"

class ResultMessage:

    __slots__ = (
        'category',
        'location',
        'message',
        'ms',
        'message_id'
    )

    def __init__(self, category: ResultCategory, location: str, message: str, ms: int, message_id: str = ""):
        self.category = category
        self.location = location
        self.message = message
        self.ms = ms
        self.message_id = message_id

    def to_dict(self) -> Dict:
        return { "category": self.category.value, "location": self.location, 
            "message": self.message, "ms": self.ms,
            "message_id": self.message_id
        }

class ResultLog():

    def __init__(self):
        self.loaded_at = udatetime.now_as_eastern()
        self.start = time.process_time_ns()

        self._messages: List[ResultLog] = []

    @property
    def messages(self) -> List[ResultMessage]:
        return self._messages

    def by_category(self, category: ResultCategory) -> List[ResultMessage]:
        return [x for x in self._messages if x.category == category]

    def add(self, category: ResultCategory, location: str, message: str,
            message_id: str = "") -> None:
        if message is None: raise Exception("Missing message")

        end = time.process_time_ns()
        delta_ms = int((end - self.start) * 1e-6)
        self.start = end

        msg = ResultMessage(category, location, message, delta_ms, message_id=message_id)
        self._messages.append(msg)

    #def error(self, location: str, message: str) -> None:
    #    self.add(ResultCategory.ERROR, location, message)
    #def warning(self, location: str, message: str) -> None:
    #    self.add(ResultCategory.WARNING, location, message)
    #def info(self, location: str, message: str) -> None:
    #    self.add(ResultCategory.INFO, location, message)

    def data_entry(self, location: str, message: str, message_id: str = "") -> None:
        self.add(ResultCategory.DATA_ENTRY, location, message, message_id=message_id)
    def data_quality(self, location: str, message: str, message_id: str = "") -> None:
        self.add(ResultCategory.DATA_QUALITY, location, message, message_id=message_id)
    def data_source(self, location: str, message: str, message_id: str = "") -> None:
        self.add(ResultCategory.DATA_SOURCE, location, message, message_id=message_id)
    def internal(self, location: str, message: str, message_id: str = "") -> None:
        self.add(ResultCategory.INTERNAL, location, message, message_id=message_id)

    # -----

    def consolidate(self):

        # build a list by ids
        ids = {}
        for i in range(len(self._messages)):
            x = self._messages[i]
            if x.message_id == "": continue
            items = ids.get(x.message_id)
            if items == None:
                ids[x.message_id] = items = []
            items.append(i)
        
        # delete anything with 10+ repeats
        to_delete = []
        for k in ids:
            items = ids[k]
            if len(items) > 10:
                idx = items[0]
                self._messages[idx].message += f" and {len(items)-1} more"
                for i in items[1:]: to_delete.append(i)

        to_delete.sort(reverse=True)
        for i in to_delete:
            del self._messages[i]

    def print(self):

        print("")

        if len(self._messages) == 0:
            print("[No Messages]")

        for cat in ResultCategory:
            messages = self.by_category(cat)
            if len(messages) == 0: continue

            print(f"=====| {cat.value.upper()} |===========")
            for x in messages:
                print(f"{x.location}: {x.message}")

        print("")


    def to_json(self) -> str:
        result = {}
        for cat in ResultCategory:
            result[cat.name] = [ x.to_dict() for x in self._messages if x.category == cat ]
        return json.dumps(result, indent=2)


    def to_frame(self) -> pd.DataFrame:

        n_total = len(self._messages)
        category = np.zeros(n_total, dtype=object)
        location = np.zeros(n_total, dtype=object)
        message = np.zeros(n_total, dtype=object)
        time_ms = np.zeros(n_total, dtype=np.int)

        idx = 0
        for cat in ResultCategory:
            messages = self.by_category(cat)
            for x in messages:
                category[idx], location[idx], message[idx], time_ms[idx] = cat.value.upper(), x.location, x.message, x.ms
                idx += 1

        df = pd.DataFrame({
            "category": category, "location": location, "message": message, "ms": time_ms
        })
        return df

    def to_csv(self) -> str:
        df = self.to_frame()
        dest = io.StringIO()
        df.to_csv(dest, index=False)
        return dest.getvalue()

    def format_table(self, cat: ResultCategory) -> List[str]:
        
        caption = f"  <h5>{cat.value.upper()}</h5>"
        df = pd.DataFrame(columns=["Location", "Message"])

        cnt = 0
        for x in self.by_category(cat):
            df.loc[df.shape[0]] = [x.location, x.message]
            cnt = cnt + 1

        if cnt == 0: return []
        
        return  [caption, df.to_html(justify='left', index=False, border=0)]

    def to_html(self, as_fragment=False) -> str:
        lines = []

        if not as_fragment:
            lines.append('  <body>')

        lines.append('    <div class="container working-results">')
        for cat in ResultCategory:
            lines.append('    <div class="row">')
            lines.extend(self.format_table(cat))
            lines.append('    </div>')
        lines.append('    </div>')

        sdate = udatetime.to_displayformat(self.loaded_at)
        lines.append(f'    <div class="timestamp">run against source at {sdate}</div>')

        if not as_fragment:
            lines.append('  </body>')

        return '\n'.join(lines)


# -----------------------------
def test():

    log = ResultLog()
    log.data_quality("NY", "Looking kinda scary.  > 50K")
    log.data_source("TX", "We're missing stuff, find it")
    log.data_entry("FL", '"Let''s Ignore It"')

    print("--- print ----")
    log.print()

    print("--- to_frame ----")
    df = log.to_frame()
    print(df)

    print("--- to_csv ----")
    s = log.to_csv()
    print(s)

    print("--- to_json ----")
    s = log.to_json()
    print(s)

    print("--- to_html ----")
    s = log.to_html()
    print(s)


if __name__ == "__main__":
    test()
