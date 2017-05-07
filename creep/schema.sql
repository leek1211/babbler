drop table if exists keywords, dictionary;
create table keywords (
  word TEXT,
  url TEXT,
  created_at INT(11)
);

create table dictionary (
	korean TEXT,
	english TEXT
)