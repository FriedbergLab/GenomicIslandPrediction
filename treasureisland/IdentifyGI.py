import pandas as pd
import numpy as np
from copy import copy
from Bio.Seq import Seq
from . import Parameters
from treasureisland.PreprocessData import PreprocessData


class IdentifyGI:

    def __init__(self, dna_sequence_list, dna_emb_model, classifier):
        '''Initialize variables'''

        self.dna_sequence_list = dna_sequence_list
        self.dna_emb_model = dna_emb_model
        self.classifier = classifier

    def get_dna_vectors(self, processed_dna_seq):
        '''Uses the DNA embedding model to get the DNA vector of a DNA segment
           processed_dna_seq : DNA segment after preprocessing step
        '''

        dna_vectors = []
        for segments in processed_dna_seq:
            inferred_vector = self.dna_emb_model.infer_vector(segments, epochs=20)
            dna_vectors.append(inferred_vector)

        return dna_vectors

    def get_dna_segment_probability(self, dna_vectors, segment_borders):
        ''' 
        Gets the probability of each DNA segment to be a GI using the classifier
        dna_vectors : DNA vectors 
        segment_borders : start and end points of DNA segments  
        '''

        probability = self.classifier.predict_proba(dna_vectors)
        prob_df = pd.DataFrame(np.column_stack([segment_borders, probability]), columns=['start', 'end', '0', '1'])
        prob_list = prob_df.values.tolist()

        return prob_list

    def get_GI_regions(self, dna_prob):
        ''' 
        Gets the DNA segments with probability above the upper threshold and 
        flanking sequences with probability between upper and lower thesholds 
        dna_prob : full list of DNA segments and their probabilities
        '''
        prev = -1
        gi_dict = {}
        gi_num = 1
        prev_gi = False
        for row in dna_prob:
            found_gi = False
            if row[3] >= Parameters.UPPER_THRESHOLD:
                found_gi = True
                if 'gi_' + str(gi_num) in gi_dict.keys():
                    gi_dict['gi_' + str(gi_num)].append(row)
                else:
                    if prev == -1:
                        gi_dict['gi_' + str(gi_num)] = [row]
                    else:
                        if prev[3] > Parameters.LOWER_THRESHOLD:
                            gi_dict['gi_' + str(gi_num)] = [prev]
                            gi_dict['gi_' + str(gi_num)].append(row)
                        else:
                            gi_dict['gi_' + str(gi_num)] = [row]
                prev_gi = True
            if found_gi == False and prev_gi == True:
                if row[3] > Parameters.LOWER_THRESHOLD:
                    gi_dict['gi_' + str(gi_num)].append(row)
                prev_gi = False
                gi_num += 1
            prev = row

        return gi_dict

    def find_fragment_probability(self, GI_borders, dna_sequence):
        '''
        Get a DNA fragment probability for class GI
        GI_borders : set of start and end points
        '''
        gi_start = int(GI_borders[0])
        gi_end = int(GI_borders[1])

        sequence = str(dna_sequence.seq).lower()
        fragment = sequence[gi_start:gi_end]
        pre_process = PreprocessData()
        kmers = pre_process.generate_kmers(fragment)

        inferred_vector = [self.dna_emb_model.infer_vector(kmers, epochs=20)]
        prob = self.classifier.predict_proba(inferred_vector)

        gi_prob = round(prob[0][1], 5)  # gi_prob probability of region belonging to class 1(GI)

        return gi_prob

    def merge(self, gi_regions, dna_sequence):
        '''
        Incrementally merge the DNA segments
        :param gi_regions: dictionary consisting of GEI regions along with flanking sequences
        :param dna_sequence: a single DNA sequence from the list of input DNA sequences
        :return: list of MergedGEI
        '''
        gi_merged_regions = []
        gi_name = 0
        for gi_id in gi_regions.keys():
            gi_region = gi_regions[gi_id]
            merged_start = merged_end = 0
            flanking_start = flanking_end = 0
            merged_probs = []
            count = 0
            for segment in gi_region:
                if count == 0: # for the first segment in the GEI region
                    if segment[3] < Parameters.UPPER_THRESHOLD: # it is a flanking sequence
                        flanking_start = [segment[0], segment[1]]
                        merged_start = gi_region[1][0]
                        count += 1
                        continue
                    else: # not a flanking sequence
                        merged_start = gi_region[0][0]
                else: # for every segment apart from first segment
                    if segment[3] < Parameters.UPPER_THRESHOLD: # check for flanking sequence at the end
                        flanking_end = [segment[0], segment[1]]
                        break
                # incrementally find prob of merged regions
                merged_prob = self.find_fragment_probability([merged_start, segment[1]], dna_sequence)
                if merged_prob >= Parameters.UPPER_THRESHOLD: # if merged region is a GEI
                    merged_end = segment[1]
                    merged_probs.append(merged_prob)
                else:  # merged region not a GEI, then save previous GEI region
                    gi_name += 1
                    if merged_probs: # if there is a previous GEI region
                        mergeObj = MergedGEI(gi_name, merged_start, merged_end, merged_probs[-1], flanking_start, flanking_end)
                        gi_merged_regions.append(mergeObj) # save previous GEI
                        flanking_start = 0 # re-initialise for next GEI
                        merged_start = segment[0]
                        merged_end = segment[1]
                        merged_probs.append(segment[3])
                    else: # the first segment categorized as GEI is not a GEI now
                        flanking_start = [segment[0], segment[1]] # let this now be a flanking segment
                        merged_start = segment[1]  # start it from the next segment
                count += 1
            if merged_end != 0: # if last GEI has not been saved
                gi_name += 1
                mergeObj = MergedGEI(gi_name, merged_start, merged_end, merged_probs[-1], flanking_start, flanking_end)
                gi_merged_regions.append(mergeObj)

        return gi_merged_regions

    def pre_fine_tune(self, mergedGEI):
        '''

        :param mergedGEI:
        :return: preFinedTuneGEI
        '''

        if mergedGEI.flanking_start != 0:
            start_limit = mergedGEI.start - (Parameters.WINDOW_SIZE / 2)
        else:
            start_limit = mergedGEI.start

        if mergedGEI.flanking_end != 0:
            end_limit = mergedGEI.end + (Parameters.WINDOW_SIZE / 2)
        else:
            end_limit = mergedGEI.end

        preFineTunedObj = PreFineTunedGEI(mergedGEI.name, mergedGEI.start, mergedGEI.end, mergedGEI.prob, start_limit, end_limit)

        return preFineTunedObj

    def fine_tune(self, preFineTunedGEI, dna_sequence):
        '''

        :param preFineTunedGEI:
        :return: fineTunedGEI
        '''

        #left border
        border_l = 1
        border_r = 0
        if preFineTunedGEI.start_limit == preFineTunedGEI.start:
            has_flanking_segment = False
        else:
            has_flanking_segment = True
        leftFineTunedGEI = self.fine_tune_helper(border_l, border_r, has_flanking_segment, preFineTunedGEI, dna_sequence)

        # right border
        border_l = 0
        border_r = 1
        if preFineTunedGEI.end_limit == preFineTunedGEI.end:
            has_flanking_segment = False
        else:
            has_flanking_segment = True

        preFineTunedGEI.start = leftFineTunedGEI.start

        rightFineTunedGEI = self.fine_tune_helper(border_l, border_r, has_flanking_segment, preFineTunedGEI, dna_sequence)

        frag_prob = self.find_fragment_probability([leftFineTunedGEI.start, rightFineTunedGEI.end], dna_sequence)

        fineTunedGEI = FineTunedGEI(preFineTunedGEI.name, leftFineTunedGEI.start, rightFineTunedGEI.end, frag_prob)

        return fineTunedGEI


    def fine_tune_helper(self, border_side_l, border_side_r, has_flanking_segment, preFineTunedGEI, dna_sequence):
        '''

        :return:
        '''

        current_obj = next_obj = FineTunedGEI(preFineTunedGEI.name, preFineTunedGEI.start, preFineTunedGEI.end,
                                              preFineTunedGEI.prob)
        significant_change = 0.1

        if has_flanking_segment:
            direction_left = border_side_l * -1
            direction_right = border_side_r * 1
            while_clause = next_obj.prob >= current_obj.prob or (current_obj.prob - next_obj.prob) < significant_change
        else:
            direction_left = border_side_l * 1
            direction_right = border_side_r * -1
            while_clause = next_obj.prob > current_obj.prob

        while(next_obj.prob >= Parameters.UPPER_THRESHOLD and
              next_obj.start >= preFineTunedGEI.start_limit and
              next_obj.end <= preFineTunedGEI.end_limit and
              (next_obj.end - next_obj.start) >= Parameters.MINIMUM_GI_SIZE and
              while_clause
        ):

            current_obj = copy(next_obj)
            next_obj.start = next_obj.start + (Parameters.TUNE_METRIC * direction_left)
            next_obj.end = next_obj.end + Parameters.TUNE_METRIC * direction_right
            frag_prob = self.find_fragment_probability([next_obj.start, next_obj.end], dna_sequence)
            next_obj = FineTunedGEI(preFineTunedGEI.name, next_obj.start, next_obj.end, frag_prob)
        return current_obj

    def find_GI_borders(self, gi_regions, id, dna_sequence):
        ''' 
        Function to combine all the GI border finding steps
        gi_regions : GI fragments along with its flanking sequence
        '''

        gi_borders = {}
        mergedGEIS = self.merge(gi_regions, dna_sequence)
        for mergedGEI in mergedGEIS:
            preFineTuned = self.pre_fine_tune(mergedGEI)
            fineTuned = self.fine_tune(preFineTuned, dna_sequence)
            gi_borders[fineTuned.name] = [id, fineTuned.start, fineTuned.end, fineTuned.prob]

        return gi_borders

    def find_gi_predictions(self):
        ''' 
        Main function to call all other functions for identifying GI regions
        '''
        all_gi_borders = []
        org_count = 0

        for dna_sequence in self.dna_sequence_list:
            org_count += 1
            print("--- sequence " + str(org_count) + "---")
            print("approximate prediction time : 2-5 minutes")
            #seq_id = ''.join(e for e in str(dna_sequence.id) if e.isalnum())
            seq_id = dna_sequence.id
            pre_process = PreprocessData()
            processed_dna_seq, segment_borders = pre_process.split_dna_sequence(dna_sequence)
            dna_vectors = self.get_dna_vectors(processed_dna_seq)
            dna_prob = self.get_dna_segment_probability(dna_vectors, segment_borders)
            gi_regions = self.get_GI_regions(dna_prob)
            gi_borders = self.find_GI_borders(gi_regions, seq_id, dna_sequence)
            all_gi_borders.append(gi_borders)

        return all_gi_borders


class MergedGEI:
    def __init__(self, name, start, end, prob, flanking_start,  flanking_end):
        self.name = name
        self.start = start
        self.end = end
        self.prob = prob
        self.flanking_start = flanking_start
        self.flanking_end = flanking_end

    def __repr__(self):
        return f"MergedGEI(name='{self.name}', start={self.start}, end={self.end},prob={self.prob}, flanking_start={self.flanking_start}, flanking_end={self.flanking_end})"


class PreFineTunedGEI:
    def __init__(self, name, start, end, prob, start_limit,  end_limit):
        self.name = name
        self.start = start
        self.end = end
        self.prob = prob
        self.start_limit = start_limit
        self.end_limit = end_limit

    def __repr__(self):
        return f"PreFineTunedGEI(name='{self.name}', start={self.start}, end={self.end},prob={self.prob}, start_limit={self.start_limit}, end_limit={self.end_limit})"


class FineTunedGEI:
    def __init__(self, name, start, end, prob):
        self.name = name
        self.start = start
        self.end = end
        self.prob = prob

    def __repr__(self):
        return f"FineTunedGEI(name='{self.name}', start={self.start}, end={self.end},prob={self.prob})"


