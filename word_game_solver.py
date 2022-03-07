import pandas as pd
import requests
import re
import os
import time

if not os.path.exists(os.path.dirname(os.path.realpath(__file__)) + '/wordle_word_list.csv'):
    # Download the word list from Wordle
    print('Word list not present in same directory, downloading from wordle')
    r = requests.get('http://www.nytimes.com/games/wordle/main.bfba912f.js')
    r = str(r.content)
    words_one = re.search('var Ma=(.*)\,Oa=', r)
    words_one = words_one.group(1)
    words_two = re.search('Oa=(.*),Ra=', r)
    words_two = words_two.group(1)
    words_one = eval(words_one)
    words_two = eval(words_two)
    wordle_word_list = words_one + words_two
    wordle_word_list.sort()
    wordle_word_list = pd.DataFrame({'words': wordle_word_list})
    wordle_word_list.to_csv(os.path.dirname(os.path.realpath(__file__)) + '/wordle_word_list.csv', index=False)
    print('Done')
else:
    print('Word list found. Loading.')


# Get wordle response for a given guess against all words in word list
# TODO fix how it deals with repeated letters
def wordle_response(guess, word_list):
    list_output = []
    for answer in word_list:
        output = ''
        for idx, letter in enumerate(guess):
            if letter == answer[idx]:
                output = output + 'G'
            elif letter in answer:
                output = output + 'Y'
            else:
                output = output + 'B'
        list_output.append(output)
    return list_output


# Drop possible answers fromt he word list based on a guess & response
def update_possible_answers(guess, response, possible_answers):
    new_possible_answers = possible_answers.copy()
    for idx, letter in enumerate(guess):
        if response[idx] == 'B' and guess.count(letter) == 1:
            # For grey/black, drop any word containing that letter, unless it's a repeated letter in the guess
            # TODO - if double letter is both B then continue to drop
            words_to_remove = [letter in word for word in new_possible_answers]
            new_possible_answers = [words for words, s in zip(new_possible_answers, words_to_remove) if not s]
        elif response[idx] == 'G':
            # For green, drop any word which doesn't have that letter in that position
            words_to_remove = [word[idx] != letter for word in new_possible_answers]
            new_possible_answers = [words for words, s in zip(new_possible_answers, words_to_remove) if not s]
        elif response[idx] == 'Y':
            # For yellow drop 1) any word which does not contain that letter
            # 2) any word with that letter in the guessed position. (Else it would be G).
            words_to_remove = [letter not in word for word in new_possible_answers]
            new_possible_answers = [words for words, s in zip(new_possible_answers, words_to_remove) if not s]
            words_to_remove = [word[idx] == letter for word in new_possible_answers]
            new_possible_answers = [words for words, s in zip(new_possible_answers, words_to_remove) if not s]
    return new_possible_answers


chosen_word_list = os.path.dirname(os.path.realpath(__file__)) + '/wordle_word_list.csv'
word_list = pd.read_table(chosen_word_list, delimiter=',')
word_list = list(word_list.iloc[:, 0])
word_list = [_.upper() for _ in word_list]

# If the best starter words, not found, calculate them

if not os.path.exists(os.path.dirname(os.path.realpath(__file__)) + '/best_starters.csv'):
    print('Best starter words not found, re-calculating, this may take several minutes')
    expected_eliminated_list = []
    for guess in word_list:
        possible_outcomes = wordle_response(guess, word_list)
        outcome_count = pd.DataFrame(possible_outcomes).value_counts()
        exp_eliminated = sum((outcome_count.sum() - outcome_count) * (outcome_count / outcome_count.sum()))
        expected_eliminated_list.append(exp_eliminated)
    best_starters = pd.DataFrame({'words': word_list, 'expected_eliminated': expected_eliminated_list})
    best_starters = best_starters.sort_values(by=['expected_eliminated'], ascending=False)
    best_starters.to_csv(os.path.dirname(os.path.realpath(__file__)) + '/best_starters.csv', index=False)
    print('Best starter words calculated and saved to file')
else:
    print('Best starter words loaded')


def solve():
    word_list = pd.read_table(chosen_word_list, delimiter=',')
    word_list = list(word_list.iloc[:, 0])
    word_list = [_.upper() for _ in word_list]
    possible_answers = word_list.copy()
    best_starters = pd.read_table(os.path.dirname(os.path.realpath(__file__)) + '/best_starters.csv', delimiter=',')
    print(f"There are {len(possible_answers)} possible words.")
    print(f"Here are the best options for your first guess \n {best_starters[:5]}")
    guess_counter = 0

    while True:
        print('Which word did you enter into Wordle?')
        guess = input()
        guess_counter += 1
        guess = guess.upper()
        # TODO input validation such as check it's 5 letters or on the word list
        print('What was the output?')
        print('  G for Green')
        print('  Y for Yellow')
        print('  B for Black/Gray')
        response = input()
        response = response.upper()
        if response == 'GGGGG':
            print(f"You won! {guess_counter} guesses")
            break

        # TODO response validation. Is it 5 letters and Y/G/B.
        possible_answers = update_possible_answers(guess, response, possible_answers)
        if len(possible_answers) == 0:
            print("There are no possible words, something went wrong.")
            break
        if len(possible_answers) == 1:
            print(f"The only possible solution is {possible_answers[0]}")
            print(f"You won! {guess_counter + 1} guesses")
            break
        print(f"After {guess_counter} guesses, there are {len(possible_answers):.0f} possible words remaining")
        print("Calculating the best choices for your next guess...")
        start_time = time.perf_counter()
        expected_eliminated_list = []

        for guess in word_list:
            possible_outcomes = wordle_response(guess, possible_answers)
            outcome_count = pd.DataFrame(possible_outcomes).value_counts()
            exp_eliminated = sum((outcome_count.sum() - outcome_count) * (outcome_count / outcome_count.sum()))
            expected_eliminated_list.append(exp_eliminated)

        best_choices = pd.DataFrame({'words': word_list, 'expected_eliminated': expected_eliminated_list})
        best_choices = best_choices.merge(pd.DataFrame({'words': possible_answers,
                                                        'solution': ['*'] * len(possible_answers),
                                                        'extra_score': [1 / len(possible_answers)] * len(
                                                            possible_answers)}),
                                          how='left', on='words')

        best_choices['solution'] = best_choices['solution'].fillna('')
        best_choices['extra_score'] = best_choices['extra_score'].fillna(0)
        best_choices['expected_eliminated'] = best_choices['expected_eliminated'] + best_choices['extra_score']
        best_choices = best_choices.drop(columns=['extra_score'])
        best_choices = best_choices.sort_values(by=['expected_eliminated', 'solution'], ascending=False).reset_index()
        end_time = time.perf_counter()
        duration = end_time - start_time
        print(f"Here are the best options for your next guess (took {duration:.1f}s). \n {best_choices[:20]}")
        if len(possible_answers) <= 10:
            print('Remaining solutions and their values:')
            print(best_choices[best_choices['solution'] == '*'])

            
solve()
