defmodule ScrapingTest do
  use ExUnit.Case
  doctest Scraping

  test "greets the world" do
    assert Scraping.hello() == :world
  end
end
